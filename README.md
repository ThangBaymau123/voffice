# Học AgentScope — Dự án thực hành

AgentScope (Alibaba Tongyi Lab) là framework Python để xây dựng ứng dụng **đa
tác tử (multi-agent)** trên nền LLM. Dự án này là 3 ví dụ tăng dần độ phức tạp,
giúp bạn nắm được toàn bộ kiến trúc.

## Kiến trúc 4 khối Lego

Mọi agent trong AgentScope đều được lắp từ 4 thành phần độc lập:

| Thành phần | Vai trò | Ví dụ class |
|---|---|---|
| **Model** | Gọi LLM (OpenAI/Claude/Qwen/Ollama). | `AnthropicChatModel`, `DashScopeChatModel` |
| **Formatter** | Chuyển danh sách `Msg` → định dạng provider hiểu. | `AnthropicChatFormatter`, `AnthropicMultiAgentFormatter` |
| **Memory** | Lưu lịch sử hội thoại (ngắn/dài hạn). | `InMemoryMemory`, `Mem0LongTermMemory` |
| **Toolkit** | Bộ công cụ agent có thể gọi (function calling). | `Toolkit`, `ToolResponse` |

`ReActAgent` ráp 4 thứ trên thành vòng lặp **Reason → Act → Observe**:
1. Reason: gọi LLM với memory + tool schema.
2. Act: nếu LLM yêu cầu gọi tool, framework gọi tool.
3. Observe: kết quả tool đi vào memory rồi lặp lại.
4. Dừng khi LLM không gọi tool nữa, hoặc đạt `max_iters`.

## Cấu hình

Project này dùng **Anthropic Claude qua AWS gateway**. Biến môi trường nằm trong
`.env` (đã `.gitignore`):

```env
ANTHROPIC_AWS_API_KEY=...
ANTHROPIC_AWS_WORKSPACE_ID=...
ANTHROPIC_AWS_BASE_URL=https://aws-external-anthropic.ap-south-1.api.aws
```

File `examples/_common.py` chứa hàm `make_model()` — nó truyền `base_url` và
header `anthropic-workspace-id` xuống `anthropic.AsyncAnthropic` qua tham số
`client_kwargs` của `AnthropicChatModel`. Đây là pattern chính thức để dùng
AgentScope với gateway tự host.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy từng ví dụ

```bash
# Windows PowerShell — đảm bảo console hỗ trợ UTF-8
$env:PYTHONIOENCODING="utf-8"

python examples/01_hello_agent.py        # ReActAgent + 2 tool built-in
python examples/02_custom_tool.py        # Tự viết tool — bạn cần hoàn thiện!
python examples/03_multi_agent_debate.py # 3 agent tranh luận qua MsgHub
```

## Lộ trình học đề xuất

### 1️⃣ `01_hello_agent.py` — Khởi động
- Chạy thử, gõ "Tính 17 * 23 giúp tôi" → quan sát agent gọi `execute_python_code`.
- Đọc code, xác định từng dòng tương ứng với khối Lego nào.

### 2️⃣ `02_custom_tool.py` — **Phần bạn code**
File có `TODO` lớn ở giữa: tự viết hàm `track_expense(amount, category, note)`.
Đây là chỗ thiết kế thực sự xảy ra — không phải boilerplate:

- **Validate hay không?** `amount > 0` báo lỗi cứng vs cho qua. An toàn vs linh hoạt.
- **Chuẩn hoá category?** `.lower().strip()` giúp gộp "Cafe" với "cafe". Đánh đổi: mất dấu vết người dùng gõ gốc.
- **Timestamp?** Có thêm `datetime.now().isoformat()` không?
- **Docstring**: LLM đọc docstring để biết khi nào gọi. Càng rõ, agent càng dùng đúng.

Sau khi hoàn thiện, chạy lại và thử:
> "Hôm nay tôi tiêu 50k cho cà phê và 200k tiền ăn trưa"
>
> "Tổng cộng tôi đã chi bao nhiêu cho cà phê?"

### 3️⃣ `03_multi_agent_debate.py` — Multi-agent
- `MsgHub` là kênh broadcast: mỗi reply của agent A tự động vào memory của B và C.
- `sequential_pipeline([a, b, c])` — phát biểu lần lượt.
- `fanout_pipeline([a, b, c])` — phát biểu song song qua `asyncio.gather` nội bộ.
- Thử `enable_auto_broadcast=False` để xem điều gì xảy ra (agent quên nhau).

## Bước tiếp theo (gợi ý mở rộng)

| Hướng | Class/Module liên quan |
|---|---|
| Bộ nhớ dài hạn (vector DB) | `Mem0LongTermMemory` |
| MCP server tools | `HttpStatelessClient` trong `agentscope.mcp` |
| Streaming token-by-token | đã bật sẵn (`stream=True`); chỉ cần in từng chunk |
| Workflow phức tạp (rẽ nhánh) | `agentscope.pipeline` các pattern `if_else`, `for_loop` |
| Đánh giá agent | `agentscope.evaluate` |

## Tham khảo

- Docs: <https://doc.agentscope.io>
- GitHub: <https://github.com/agentscope-ai/agentscope>
- Phiên bản đang dùng: **1.0.20**
