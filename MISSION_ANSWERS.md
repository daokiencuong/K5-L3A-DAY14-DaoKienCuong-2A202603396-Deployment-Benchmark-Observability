# Day 14 — Mission Answers

**Họ tên:** Đào Kiên Cường  
**MSSV:** 2A202603396  
**Lớp:** K5-L3A

> Ghi câu trả lời và bằng chứng do chính mình thu thập. Không điền số đo ước lượng. Che token và secret trước khi dán output.

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns

1. API key và URL database được hardcode trong `01-localhost-vs-production/develop/app.py`; commit source có thể làm lộ secrets.
2. `DEBUG = True`, `reload=True` và cấu hình không tách theo môi trường; chạy production có thể bật chế độ debug và restart không cần thiết.
3. App chỉ bind `localhost` và dùng cố định cổng 8000 nên không phù hợp để nhận traffic từ bên ngoài container hoặc nền tảng cloud.
4. Dùng `print()` để log request/response; một dòng còn in API key ra log.
5. Không có health/readiness endpoint, nên platform không biết app còn sống hay đã sẵn sàng.
6. Không có quản lý lifecycle/graceful shutdown để dọn tài nguyên và chờ request đang chạy.

### Exercise 1.2 — Chạy bản develop

- Gọi ASGI app bằng FastAPI `TestClient` trong môi trường này: `POST /ask?question=Hello` → **200**; nhận được câu trả lời mock.
- Khi thử chạy Uvicorn trực tiếp trên Windows, hệ điều hành trả `WinError 10013` khi mở cổng local; vì vậy kết quả trên là kiểm tra in-process, không phải request qua socket.

### Exercise 1.3 — So sánh develop và production

| Hạng mục | Develop | Production | Vì sao quan trọng |
|---|---|---|---|
| Cấu hình | Giá trị hardcode trong source | Đọc biến môi trường qua `config.py` | Có thể thay cấu hình theo môi trường mà không sửa code |
| Secret | Key/DB URL nằm trong source; log key | Không log secret; hỗ trợ cấu hình an toàn | Tránh lộ credential trong Git và log |
| Logging | `print()` và debug output | Log có cấu trúc JSON | Dễ tìm kiếm, lọc và theo dõi trên hệ thống log |
| Health/readiness | Không có endpoint | Có `/health` và `/ready` | Phân biệt process còn sống với app sẵn sàng nhận traffic |
| Shutdown | Không quản lý lifecycle | Lifespan có startup/shutdown | Đóng tài nguyên và giảm nguy cơ cắt request khi deploy |
| Network/runtime | `localhost`, cổng cố định, reload bật | Host/port lấy từ config, bind được cho container | Cho phép platform route traffic và inject port |

- Bản production được gọi với lifespan startup/shutdown: `/health` **200**, `/ready` **200**.

## Part 2 — Docker

### Exercise 2.1 — Dockerfile

1. Base image của develop là `python:3.11`.
2. Working directory là `/app`.
3. Copy `requirements.txt` trước source để Docker có thể tái sử dụng layer cài dependencies khi chỉ code thay đổi.
4. `CMD` đặt lệnh mặc định có thể bị thay bằng lệnh lúc chạy container. `ENTRYPOINT` đặt executable chính; đối số lúc chạy thường được nối vào entrypoint.

### Exercises 2.2–2.3 — Build, chạy và so sánh image

- Kết quả gọi develop container: `POST /ask?question=What%20is%20Docker` qua cổng host 18080 → **200**.
- Kích thước `my-agent:develop` (`docker images`): **1.67 GB** (inspect: 1,667.8 MB).
- Kích thước `my-agent:advanced` (`docker images`): **240 MB** (inspect: 239.8 MB).
- Image production giảm khoảng **85.6%**: `(1,667.8 − 239.8) / 1,667.8 × 100`.
- Multi-stage: builder cài dependencies và build tools; runtime slim chỉ nhận packages và code cần chạy. Nhờ không mang compiler/build packages sang runtime nên image nhỏ hơn.

### Exercise 2.4 — Compose và Nginx

- Sơ đồ: `Client → Nginx (:80) → Agent`; Agent kết nối Redis và Qdrant trong network nội bộ. Nginx reverse-proxy request đến Agent; Redis lưu dữ liệu/cache; Qdrant là vector database.
- Qua Nginx: `GET /health` → **200**; `POST /ask` với JSON body → **200**.
- Lưu ý: app `develop` trong Part 1 và 2 dùng query `?question=...`; app production trong Compose nhận JSON body.

## Part 3 — Cloud Deployment

- Nền tảng: **Render** — Blueprint `06-lab-complete/render.yaml`, gồm web service `day14-agent` (Docker, region Singapore) và Key Value `day14-redis`.
- URL public của agent Part 6: **https://day14-agent-179v.onrender.com**
- Kết quả smoke check cloud: `GET /health` → **200** (`{"status":"ok","environment":"production"}`); `GET /ready` → **200** (`{"ready":true}`); `POST /ask` không key → **401**; `POST /ask` có key → **200**.
- Biến môi trường đặt trên Render (chỉ tên, không ghi giá trị): `AGENT_API_KEY` (generateValue), `REDIS_URL` (lấy từ Key Value), `RATE_LIMIT_PER_MINUTE=10`, `DAILY_BUDGET_USD=10.0`, `ENVIRONMENT=production`; `PORT` do Render cấp.
- So sánh: `railway.toml` khai báo Dockerfile builder, health-check `/health` và restart khi lỗi; `render.yaml` là Blueprint mô tả cả web service lẫn Redis, liên kết `REDIS_URL`, sinh `AGENT_API_KEY`, chọn vùng Singapore và health-check. Railway thuận tiện để tạo project/service từ CLI; Render Blueprint thể hiện hạ tầng nhiều service trong một file cấu hình.
- Cloud Run pipeline: Cloud Build chạy tests trước, rồi build image theo `$COMMIT_SHA` và `latest`; tiếp theo push image lên Container Registry. Cuối cùng `gcloud run deploy` phát hành image theo commit vào `asia-southeast1`, cấu hình scale, CPU/RAM, timeout và đọc secret từ Secret Manager. `service.yaml` mô tả service Cloud Run, concurrency, giới hạn tài nguyên và autoscaling.
- Ảnh: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`.

## Part 4 — API Security

### Exercises 4.1–4.3 — API key, token và rate limit

- Exercise 4.1 develop, thiếu API key → **401**; với API key đã cấu hình trong process → **200**.
- Bản production: thiếu bearer token tại `POST /ask` → **401**. Lấy token bằng user `student` qua `/auth/token`; token không được ghi vào report.
- Gửi 11 request liên tiếp bằng token student trong cửa sổ test: 10 request đầu **200**, request thứ 11 **429**. Giới hạn user là 10 request/phút.
- JWT có thời hạn 60 phút; limiter demo lưu trạng thái trong memory nên chỉ phù hợp minh họa, không chia sẻ trạng thái giữa nhiều worker/instance.

### Exercise 4.4 — Cost guard

Cost guard kiểm tra budget trước khi gọi LLM; sau khi có response thì ước tính token/cost và cộng vào usage. Bản demo đặt giới hạn $1/ngày mỗi user và $10/ngày toàn cục: vượt giới hạn user trả **402**, vượt global budget trả **503**. Rate limit chặn tần suất gọi; cost guard chặn chi phí. Bản demo lưu counters trong memory, còn production cần lưu bền vững/chia sẻ qua Redis hoặc database.

## Part 5 — Scaling & Reliability

### Exercises 5.1–5.2 — Health checks và graceful shutdown

- `/health` là liveness: xác nhận process hoạt động để orchestrator quyết định restart nếu app chết. `/ready` là readiness: chỉ nhận traffic sau khi startup/dependencies sẵn sàng.
- Bản develop chạy lifecycle startup/shutdown; shutdown chuyển readiness về false và chờ tối đa 30 giây cho request đang xử lý. Đã mô phỏng một request đang in-flight; shutdown log trạng thái chờ rồi hoàn tất sau khi request được đánh dấu xong. Chưa gửi SIGTERM qua một server đang mở socket vì môi trường Windows chặn bind local.
- Khi chạy ví dụ develop, `/health` → **200**, `/ready` sau startup → **200**.

### Exercises 5.3–5.5 — Stateless, load balancing và test

- Chạy Compose với 3 agent, Redis và Nginx (`-p k5-day14-scaling`); `test_stateless.py` gửi 5 câu trong cùng session. Cả **3 instance** đều phục vụ request; đọc lại history nhận đủ **10 message** (5 câu hỏi + 5 câu trả lời).
- Kết quả xác nhận session được lưu trong Redis, nên request kế tiếp có thể tới instance khác mà không mất history.
- Nếu giữ state trong RAM, instance khác không có session đó; khi load balancer chuyển request hoặc instance restart, history sẽ mất/không tìm thấy.
- Sau bài, stack đã được dừng bằng `docker compose ... down -v`.

## Part 6 — Final Project

- Lệnh kiểm tra đầy đủ: `cd 06-lab-complete; python check_production_ready.py`
- Checker đã chạy đầy đủ trong Ubuntu WSL2 với Docker; kết quả **12/12 tiêu chí, 41/41 checks passed**.

```text
✅ Dockerfile (multi-stage, < 500 MB)
✅ docker-compose.yml (agent + redis)
✅ .dockerignore
✅ Health check endpoint (GET /health)
✅ Readiness endpoint (GET /ready)
✅ API Key authentication
✅ Rate limiting
✅ Cost guard
✅ Config từ environment variables
✅ Structured logging
✅ Graceful shutdown
✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 41/41 checks passed
PASS 12/12 — PRODUCTION READY
```

## AI log

| Ngày | Phần/code | Câu hỏi đã hỏi AI | Gợi ý nhận được | Tôi đã tự sửa và kiểm tra thế nào |
|---|---|---|---|---|
| 2026-11-25 | Part 6 — `06-lab-complete/` | Hoàn thiện agent theo 12 tiêu chí production readiness | Thiết kế env config, API key, Redis sliding-window rate limit/cost guard, health/readiness, JSON logging, graceful shutdown, Docker multi-stage/Compose và Railway config | Tự rà code, không sửa checker; chạy đầy đủ `check_production_ready.py` trong Ubuntu WSL2: 12/12 tiêu chí, 41/41 checks passed; Docker stop exit code 0 trong 0.7 giây |
| 2026-11-25 | Part 7 — observability + đóng gói | Cách chạy stack, lấy trace/alert và điền báo cáo | Lệnh Compose, PromQL/API Prometheus, API Jaeger v3, cách đối chiếu CSV/JSON | Tự chạy stack `k5-day14-observability`, tạo tải bằng Locust, chụp 4 ảnh, lấy `trace_id` và log JSON thật, đối chiếu số liệu với CSV/JSON trước khi điền report |
