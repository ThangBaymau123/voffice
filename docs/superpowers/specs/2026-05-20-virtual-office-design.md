# Virtual Office — Design Spec

- **Date:** 2026-05-20
- **Status:** Design approved, pending implementation plan
- **Owner:** Thang
- **Framework:** AgentScope 1.0.20 (Python 3.10) + FastAPI

## 1. Mục tiêu

Xây dựng phòng chat **văn phòng phần mềm ảo** gồm 1 Manager + 4 nhân viên
(Product Manager, Backend Dev, Frontend Dev, QA Tester). Người dùng nhập việc;
Manager phân công; cả 4 nhân viên cùng "ngồi chung phòng" (open office) và có
thể chen ý kiến phản biện kỹ thuật.

Hai entry point cùng dùng chung logic:
- **CLI** — `examples/04_virtual_office_cli.py`
- **Web UI** — `examples/05_virtual_office_web.py` (FastAPI + WebSocket,
  giao diện Slack/Discord-style, dark theme)

## 2. Non-goals (out of scope)

- Không authentication / multi-user.
- Không persist hội thoại giữa các phiên (mọi memory là `InMemoryMemory`).
- Không tool calling cho employee — họ chỉ phát biểu (text), chưa cần đọc file
  hay chạy code.
- Không hệ thống KPI / chấm điểm.
- Không upload file, không render markdown phức tạp (plain text + xuống dòng).

## 3. Kiến trúc tổng thể

```
┌─ Browser ─────────────────────────────────────────────┐
│  Sidebar (5 agent với chấm online)                    │
│  Chat feed (stream token real-time)                   │
│  Input box                                            │
└────────┬──────────────────────────────────────────────┘
         │  WebSocket /ws
         ▼
┌─ FastAPI (web/server.py) ─────────────────────────────┐
│  GET /     → index.html                               │
│  GET /static/*                                        │
│  WS  /ws   → 1 connection = 1 office session          │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌─ office_engine.py (logic dùng chung CLI + Web) ───────┐
│  build_office() → {manager, employees, hub}           │
│  run_turn(office, user_msg)                           │
│      async generator yield                            │
│         (speaker_name, text_chunk, is_final)          │
└────────┬──────────────────────────────────────────────┘
         │
         ▼
┌─ AgentScope ─────────────────────────────────────────┐
│  MsgHub(participants=[manager + 4 employees],         │
│         enable_auto_broadcast=True)                   │
│  Mỗi vòng:                                            │
│    1. hub.broadcast(user_msg)                         │
│    2. await manager(...) → message broadcast tự động  │
│    3. fanout_pipeline(employees) → 4 reply song song  │
│    4. yield từng reply (lọc [skip])                   │
└───────────────────────────────────────────────────────┘
```

## 4. Components

### 4.1 `examples/_common.py` (mở rộng)

```python
def make_model(
    api_key: str | None = None,
    workspace_id: str | None = None,
    base_url: str | None = None,
    *,
    model_name: str = "claude-sonnet-4-5",
    stream: bool = True,
) -> AnthropicChatModel: ...
```

Nếu tham số `None` → fallback sang `ANTHROPIC_AWS_*` env vars (giữ tương
thích examples 1–3). Cho phép truyền custom để mỗi employee có key/region
riêng (Employee 4 thuộc `ap-northeast-2` nên `base_url` khác).

### 4.2 `examples/office_engine.py`

| Hàm/Class | Chữ ký | Trách nhiệm |
|---|---|---|
| `ROLES` | `dict[str, RoleSpec]` | name → (title, sys_prompt, env_prefix) |
| `RoleSpec` | dataclass | `title`, `sys_prompt`, `env_prefix` |
| `build_office()` | `() -> Office` | Đọc env, dựng 5 `ReActAgent` + `MsgHub` |
| `run_turn(office, msg)` | `async generator` | Yield `TurnEvent(speaker, text_chunk, is_final)` |
| `Office` | dataclass | `manager: ReActAgent`, `employees: list[ReActAgent]`, `hub: MsgHub` |
| `TurnEvent` | dataclass | `speaker: str` (tên agent), `text_chunk: str` (**delta** từ stream, KHÔNG phải cumulative), `is_final: bool` (`True` ở chunk cuối của 1 speaker) |

Client kết hợp chunks bằng cách: khi nhận event với speaker mới (hoặc speaker
khác chunk trước), tạo bubble mới; mỗi chunk append vào bubble hiện tại; khi
`is_final=True` đóng bubble đó.

`run_turn` flow:
1. `await hub.broadcast(Msg("User", msg, "user"))`
2. `manager_reply = await manager(None)` — yield từng chunk khi stream
3. `replies = await fanout_pipeline(employees)`
4. Với mỗi reply: nếu `text.strip() == "[skip]"` → bỏ qua; ngược lại yield

### 4.3 `examples/04_virtual_office_cli.py`

REPL terminal, dùng colorama:
- Manager: cyan
- Lan (PM): yellow
- Minh (Backend): green
- Hà (Frontend): magenta
- Tú (QA): blue

Mỗi `TurnEvent` → `print(f"[{speaker}] {chunk}", end="", flush=True)`.
Gõ `exit` hoặc `Ctrl+C` để thoát.

### 4.4 `examples/05_virtual_office_web.py`

```python
import uvicorn
import webbrowser
from web.server import app

if __name__ == "__main__":
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

### 4.5 `web/server.py`

```python
app = FastAPI()
app.mount("/static", StaticFiles(directory="web/static"))

@app.get("/")
async def index() -> FileResponse: ...

@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    office = build_office()
    while True:
        data = await websocket.receive_json()  # {"text": "..."}
        async for event in run_turn(office, data["text"]):
            await websocket.send_json({
                "speaker": event.speaker,
                "text": event.text,
                "final": event.is_final,
            })
```

1 WebSocket = 1 phiên văn phòng (mỗi tab browser có Office riêng).

### 4.6 `web/static/`

- **`index.html`** — Layout 2 cột: `<aside id="roster">` (sidebar) + `<main id="chat">`
  (feed + input). Loaded `app.js` qua `<script type="module">`.
- **`app.js`** — Vanilla JS (không build step). Mở `new WebSocket("ws://" + location.host + "/ws")`,
  parse JSON, append/grow `<div class="msg" data-speaker="...">` cho mỗi event.
- **`style.css`** — Dark palette: bg `#1e1f22`, surface `#2b2d31`, text `#dbdee1`,
  accent xanh `#5865f2`. Avatar = chữ cái đầu trong vòng tròn màu theo agent.

## 5. Data flow chi tiết (1 vòng)

```
USER: "Cần API đăng nhập 2FA"
   │
   ├─ WebSocket → server.py → run_turn(office, "Cần API đăng nhập 2FA")
   │
   ├─ hub.broadcast(Msg("User", "...", "user"))
   │     (5 agent memory đều có msg này)
   │
   ├─ await manager(None)
   │     yield events stream:
   │       (Manager, "Lan, lên user story.", false)*
   │       (Manager, " Minh, thiết kế endpoint.", false)*
   │       (Manager, " Tú, viết acceptance criteria.", true)
   │     (Auto-broadcast → 4 employee memory)
   │
   ├─ await fanout_pipeline([Lan, Minh, Hà, Tú])
   │     replies song song:
   │       Lan:  "User story: ..."     → yield
   │       Minh: "API: POST /auth/..." → yield
   │       Hà:   "[skip]"              → KHÔNG yield
   │       Tú:   "AC: ..."             → yield
   │
   └─ Kết thúc 1 vòng
```

## 6. Cấu hình môi trường

File `.env` (đã `.gitignore`):

```env
# Fallback (cho examples 1-3 cũ và Manager tạm thời)
ANTHROPIC_AWS_API_KEY=...
ANTHROPIC_AWS_WORKSPACE_ID=...
ANTHROPIC_AWS_BASE_URL=...

# 4 nhân viên
EMPLOYEE_1_KEY=...        # PM (Lan)
EMPLOYEE_1_WORKSPACE=...
EMPLOYEE_1_BASE_URL=...

EMPLOYEE_2_KEY=...        # Backend (Minh)
EMPLOYEE_2_WORKSPACE=...
EMPLOYEE_2_BASE_URL=...

EMPLOYEE_3_KEY=...        # Frontend (Hà)
EMPLOYEE_3_WORKSPACE=...
EMPLOYEE_3_BASE_URL=...

EMPLOYEE_4_KEY=...        # QA (Tú) — region ap-northeast-2
EMPLOYEE_4_WORKSPACE=...
EMPLOYEE_4_BASE_URL=https://aws-external-anthropic.ap-northeast-2.api.aws

# Manager — placeholder; khi có key thứ 5 thì đổi
MANAGER_KEY=${ANTHROPIC_AWS_API_KEY}
MANAGER_WORKSPACE=${ANTHROPIC_AWS_WORKSPACE_ID}
MANAGER_BASE_URL=${ANTHROPIC_AWS_BASE_URL}
```

## 7. System prompts

### 7.1 Manager
```
Bạn là Manager của một văn phòng phần mềm 4 người: Lan (PM), Minh (Backend),
Hà (Frontend), Tú (QA). Khi user đăng việc:
  1. Phân tích yêu cầu.
  2. Giao việc CỤ THỂ cho từng người liên quan (ít nhất 1, nhiều nhất 4),
     gọi đích danh.
  3. Không tự làm thay — chỉ điều phối.
Trả lời ngắn (2-5 câu), tiếng Việt.
```

### 7.2 Mỗi employee (template chung)
```
Bạn là {Name}, {Title} trong văn phòng phần mềm.

QUY TẮC NÓI:
- Nếu Manager nhắc tên bạn → trả lời chi tiết theo chuyên môn.
- Nếu Manager giao cho người khác nhưng bạn thấy LỖI KỸ THUẬT NGHIÊM TRỌNG
  trong cách tiếp cận, hãy chen ngắn 1-2 câu phản biện.
- Nếu không có gì để góp, trả lời CHÍNH XÁC chuỗi: [skip]

Trả lời tiếng Việt, 2-4 câu, từ góc nhìn chuyên môn ({Title}) của bạn.
```

## 8. Error handling

| Lỗi | Vị trí | Hành vi |
|---|---|---|
| Missing env var | startup | `KeyError` với tên var → exit 1 |
| Invalid API key | first call | In `⚠️ <Name> không kết nối được` → tiếp tục REPL |
| Rate limit / 5xx | mỗi agent call | `try/except` quanh từng `await agent(...)`, in cảnh báo |
| WebSocket disconnect | server | Log + close socket; server vẫn chạy |
| Ctrl+C / `exit` | CLI | Thoát sạch, không stacktrace |
| Agent trả `[skip]` | engine | Bỏ qua không yield |

Không catch lỗi nội bộ AgentScope (format/memory) — để nổi lên vì đó là bug.

## 9. Testing — manual scenarios

| # | Scenario | Kỳ vọng |
|---|---|---|
| 1 | CLI: 5 key hợp lệ, khởi động | Banner + 5 dòng "✓ \<Name\> online" |
| 2 | CLI: thiếu `EMPLOYEE_3_KEY` | `Missing: EMPLOYEE_3_KEY` → exit 1 |
| 3 | CLI: "Cần API đăng nhập" | Manager phân ≥ 2 NV; Backend (Minh) chi tiết |
| 4 | CLI: "Viết test plan thanh toán" | Manager chỉ định Tú; 3 NV khác `[skip]` |
| 5 | CLI: "Lưu mật khẩu plaintext" | Tú hoặc Minh chen ngang phản đối |
| 6 | CLI: `exit` | Thoát sạch |
| 7 | Web: mở browser tự động | `http://localhost:8000` load page, sidebar có 5 chấm xanh |
| 8 | Web: gõ task | Bubble manager + employee xuất hiện stream token |
| 9 | Web: disconnect WS giữa chừng | Server không crash, refresh là tiếp tục được |
| 10 | Web: 2 tab cùng lúc | Mỗi tab có Office riêng, không lẫn message |

## 10. Done criteria

- ✅ Cấu trúc file đúng như Section 4.
- ✅ 10 scenario Section 9 đều pass khi chạy tay.
- ✅ Mọi function < 50 dòng, mọi file < 250 dòng.
- ✅ `README.md` cập nhật mục "Ví dụ 4 (CLI) & 5 (Web)".
- ✅ `.env.example` thêm 5 dòng key mẫu (placeholder, không có secret thật).
- ✅ Sau mỗi token nhận về, browser hiển thị trong < 100ms (perceived realtime).

## 11. Bước tiếp theo

Sau khi spec được phê duyệt, skill `superpowers:writing-plans` sẽ chia work
thành các milestone cụ thể (mỗi milestone ~30-60 phút code).
