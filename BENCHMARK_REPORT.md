# Benchmark & Observability Report — Day 14

**Người thực hiện:** Đào Kiên Cường  
**Ngày chạy:** 2026-11-25  
**Môi trường:** Windows, Python 3.11 virtual environment, agent chạy local bằng Uvicorn; mock LLM, `mock-llm-small`, không dùng API key. Mỗi load run có 300 request. Kết quả JSON và log nằm trong `06-lab-complete/benchmark-observability/develop/reports/`. Phần observability chạy bằng Docker Desktop 29.9.3 (Compose v5.7.1), project `k5-day14-observability`: 2 agent + Nginx + Prometheus + Grafana + Jaeger + Locust.

> Đây là benchmark local một lần chạy trên máy phát triển; số liệu không phải cam kết production. Random mock latency/error và tải đồng thời trên cùng host làm kết quả biến thiên.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng |
|---|---:|---|
| p95 latency `/ask` | ≤ 500 ms | Giữ phần lớn request trong nửa giây, đồng thời theo dõi tail riêng bằng p99. |
| Error rate `/ask` | ≤ 2% | Cho phép một lượng nhỏ lỗi upstream mock; vượt ngưỡng thì cần giảm tải hoặc xử lý dependency. |
| Accuracy trên golden dataset | 100% sau chỉnh KB | Bộ dữ liệu lab nhỏ, nên dùng làm quality gate hồi quy chặt cho các câu đã biết. |

## 2. Benchmark hiệu năng

### 2.1 Concurrency vs latency — agent v2

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO p95 / error |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.89 | 202.3 | 250.3 | 1,704.1 | 0.67% | PASS / PASS |
| 10 | 36.54 | 198.3 | 257.1 | 1,718.3 | 2.33% | PASS / FAIL |
| 50 | 90.99 | 217.1 | 894.4 | 1,727.0 | 0.00% | FAIL / PASS |
| 100 | 41.43 | 938.3 | 4,705.9 | 5,230.3 | 1.00% | FAIL / PASS |

RPS tăng đến concurrency 50 rồi giảm mạnh ở 100; đồng thời p95/p99 tăng rõ. Trên cấu hình local này, mức 100 đã quá tải và mức 50 cũng không đạt SLO latency. Concurrency 10 vượt error budget trong lần chạy này do lỗi upstream ngẫu nhiên; cần lặp benchmark trên host ổn định hơn trước khi kết luận về ngưỡng tải cố định.

### 2.2 Tail latency — concurrency 20, mỗi cấu hình 300 request

| `MOCK_SLOW_RATE` của agent | Avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 202.6 | 246.9 | 251.1 |
| 0.03 | 255.2 | 251.6 | 1,700.5 |
| 0.1 | 355.5 | 1,689.0 | 1,734.0 |

Ở 3% slow requests, p99 nhạy hơn p95 vì tỷ lệ request chậm còn nằm gần phần 1% cuối phân phối; ở 10%, tail đủ lớn để kéo p95 lên. Average cũng bị kéo tăng nhưng che khuất người dùng chịu latency cao, nên SLO cần theo percentile. Mỗi dòng có JSON riêng `load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json` (bản chạy lại sạch; lần chạy đầu lưu `load_v2_slow_*_initial.json` vì agent chưa restart hẳn nên mọi cấu hình đều còn tail ~1,7 s).

## 3. Benchmark chất lượng — golden dataset 23 câu

| Chỉ số | Agent v1 | Agent v2 ban đầu | Agent v2 sau sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 58.4 | 109.0 | 113.0 |
| Tổng cost mock | $0.000422 | $0.000759 | $0.000785 |
| Cost / câu đúng | $0.00042195 | $0.00003616 | $0.00003413 |
| Quality gate | FAIL | PASS ở ngưỡng 80% | PASS ở ngưỡng 100%, không regression |

Hai câu v2 trả lời sai lúc đầu là `security-02` (JWT và API key) và `scaling-03` (Kubernetes HPA). Đã thêm tài liệu kích hoạt cho JWT/API key với các ý token, thời hạn và chữ ký; đồng thời bổ sung HPA với CPU, memory và custom metrics trong `develop/utils/mock_llm.py`. Eval cuối so sánh với `eval_v2.json`, đạt 23/23 và không làm câu đã đúng bị regression.

V2 dùng nhiều token hơn v1 và tổng cost cao hơn vì trả lời có ngữ cảnh; nhưng chất lượng tăng mạnh, làm cost trên mỗi câu đúng giảm khoảng một bậc độ lớn. P95 trong eval dùng mẫu 23 câu nên không đại diện latency; ví dụ eval cuối có một slow request và p95 1,520 ms, do đó dùng kết quả load test 300 request để đánh giá hiệu năng.

## 4. Observability stack

Stack được chạy bằng `docker compose -p k5-day14-observability up -d --build --scale agent=2` (Grafana publish ra cổng `3001` vì cổng `3000` trên máy đang bận; dashboard và dữ liệu không đổi). Prometheus scrape 2 agent, Jaeger nhận trace qua OTLP/HTTP, Locust tạo tải 100 user.

### 4.1 Bằng chứng

- [x] Dashboard Grafana khi có tải — `screenshots/grafana-dashboard.png`: Traffic **60,6 req/s**, Error rate **0,90%**, p95 **458 ms**, in-flight **16**, **2 instance**, LLM cost **$0,2264/h**.
- [x] Trace chậm trong Jaeger — `screenshots/jaeger-slow-trace.png`: trace `2f7847b...`, tổng **1,8 s**, span `chat mock-llm-small` chiếm **1,7 s**.
- [x] Trace lỗi trong Jaeger — `screenshots/jaeger-error-trace.png`: trace `2a380ca...`, span `chat mock-llm-small` có event `exception` với `exception.message=Upstream LLM error: 503 Service Unavailable (mock)`.
- [x] Prometheus alert đang firing — `screenshots/prometheus-alert-firing.png`: **3 alert firing** cùng lúc (`AgentHighErrorRate`, `AgentHighLatencyP95`, `LLMCostBurnRateHigh`).

### 4.2 Thí nghiệm fault injection

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~2 phút (đổi 20:17:40 → firing 20:19:42) | Error rate ~**19%** (`value=0.1894`); Locust ghi **864 lỗi 503 / 4.409** request `/ask` |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~3 phút (đổi 20:17:40 → firing 20:20:42) | p95 ~**1,94 s** (`value=1.94`); CSV `fault_slow_0_3_stats.csv`: p95 **1.700 ms**, avg **694,5 ms** |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | Đang firing, duy trì suốt lần chạy (activeAt 20:18:22); cost burn ~**$33,05/h** | Cost burn (USD/giờ); `fault_large_model_stats.csv`: p95 **560 ms**, avg **490,8 ms** |
| D | `docker pause` agent-2 | `AgentInstanceDown` | **~38 giây** (pause 20:21:54 → firing 20:22:32; activeAt 20:22:02) | Instances up **2 → 1**; Locust ghi **86 lỗi 504** tại Nginx nhưng Error rate của agent vẫn xanh |
| E | `AGENT_VERSION=v1` | Không có alert hạ tầng | — | Retrieval hit ratio và tokens/s giảm; infra metric vẫn xanh nên không phát hiện được |

Số liệu alert A–D lấy từ lần chạy fault tổng hợp 100 user trong 4 phút; CSV tương ứng ở `06-lab-complete/benchmark-observability/production/benchmark-results/evidence_fault_stats.csv` (2.020 lỗi 503 và 86 lỗi 504). Alert C kế thừa trạng thái từ lần chạy trước nên mốc `activeAt` sớm hơn thời điểm đổi model.

**Thí nghiệm E không làm alert nào firing. Phát hiện loại sự cố này trong production bằng cách nào?**

Phải chạy **eval trên golden dataset trong CI** trước khi deploy (quality gate accuracy 100%, không regression như `develop/reports/eval_v2_fixed.json`), đồng thời theo dõi các metric chất lượng: retrieval hit ratio, token/câu, cost/câu đúng và panel version đang chạy. Alert hạ tầng chỉ bắt lỗi 5xx/latency/cost, không bắt được câu trả lời sai.

### 4.3 Debug bằng trace

Trace chậm nhất trong lần chạy:

- `trace_id`: `2f7847bba09e7fb8b994eaffdc10edee`
- Tổng thời gian: **1.819,4 ms**
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` — **1.661 ms** (~**91,3%** tổng trace); `agent.retrieve_context` chỉ 86,1 ms.
- Dòng log JSON tương ứng (cùng `trace_id`):

```json
{"ts": "2026-11-25T13:15:58.160958+00:00", "level": "INFO", "service": "observable-agent", "instance": "3fb181451ba3", "event": "llm_call", "trace_id": "2f7847bba09e7fb8b994eaffdc10edee", "span_id": "5a550d941d0aaa07", "request_id": "782342b5d857", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1661.4}
```

Trace lỗi tương ứng (dùng cho mục 4.1): `trace_id=2a380ca9cd792391dc389808b5def5eb`, tổng **866,8 ms**, span `chat mock-llm-small` **841,9 ms** có event `exception` (`utils.mock_llm.LLMError: Upstream LLM error: 503 Service Unavailable (mock)`). Log cùng trace:

```json
{"ts": "2026-11-25T13:15:59.197808+00:00", "level": "INFO", "service": "observable-agent", "instance": "3fb181451ba3", "event": "llm_error", "trace_id": "2a380ca9cd792391dc389808b5def5eb", "span_id": "20cb07800d62c0bf", "request_id": "dd7ccff6a6fe", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling — Locust headless

| Số instance | RPS | p50 / p95 / p99 (ms) | Failures |
|---:|---:|---|---:|
| 1 | 65.60 | 190 / 340 / 1700 | 73 / 7.802 (0,94%) |
| 3 | 65.83 | 190 / 230 / 1700 | 74 / 7.836 (0,94%) |

Hai lần chạy dùng `locust --headless -u 100 -r 10 -t 2m`, mỗi lần 2 phút; số liệu lấy từ dòng `Aggregated` của `scale_1_stats.csv` và `scale_3_stats.csv` (gồm cả `/health`, chiếm khoảng 9% request). Scale từ 1 lên 3 instance gần như không tăng RPS (65,60 → 65,83) và chỉ cải thiện p95 (340 → 230 ms), trong khi p99 vẫn 1.700 ms. Nút thắt không nằm ở số instance mà ở latency của LLM mock và số user cố định của Locust: mỗi request `/ask` chờ mock LLM, nên thêm instance không làm tăng throughput khi 100 user đã bão hoà. Muốn tăng RPS cần tăng tải hoặc tối ưu dependency LLM/retrieval, không chỉ scale ngang agent.

## 6. Kết luận

1. p95/p99 cho thấy tail latency và điểm quá tải rõ hơn average; benchmark này vượt SLO p95 ở concurrency 50 và 100.
2. Golden dataset chặn được hai lỗi retrieval; quality gate cuối đạt 100% sau khi bổ sung hai mục trong KB.
3. Mock benchmark có ngẫu nhiên và mẫu lab nhỏ; cần lặp lại trên môi trường được kiểm soát trước quyết định production.

Trong production thật, cần bổ sung theo dõi saturation (CPU, memory, queue/in-flight requests), timeout/retry theo dependency, SLO burn-rate alerts và cost theo tenant/model. CP8 đã hoàn tất: stack, dashboard, traces, alerts, Locust CSV, fault injection và screenshots đều có trong repo.
