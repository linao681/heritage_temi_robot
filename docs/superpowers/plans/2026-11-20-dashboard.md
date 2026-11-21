# Local dashboard implementation

Goal: native Tk desktop dashboard (no web server/dependency), live ROS2 robot/tour/visitor/navigation status, virtual eight-station map and QA/alerts, explicit Mock-only pause/resume/cancel/takeover. No direct motor commands or autonomous actions. Default read-only; enable controls only in explicit local test domain, fresh mock_map and tour telemetry, state-appropriate commands. Display accepted/rejected/timeout independently from actual robot state. Alternative browser dashboard would add hosting and control exposure; defer it.

- Write model tests for stale/malformed telemetry, freshness, display fallback and control gating; then implement.
- Add ROS2 subscriptions and bounded async service bridge; test actual local gateway/tour communication and rejection/read-only mode.
- Implement Tk interface with no blocking event loop, route progress and Mock map; build, run full regression and UI smoke/demo; record evidence and update docs.
