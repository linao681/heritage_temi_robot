# T08浏览器视觉检查记录

状态：`NOT_RUN`

- 两次尝试通过桌面浏览器自动化连接当前任务标签超时；没有取得页面截图。
- 本机 Firefox 157.0.1存在。两次临时profile截图启动均因Firefox Snap无法识别未初始化profile目录而退出，原始日志为 `replay-firefox.log`、`replay-firefox-run-002.log`；没有生成截图。
- 只读进程检查发现已有Firefox进程 `/snap/firefox/9036/usr/lib/firefox/firefox`（PID 500081）；没有连接或控制该浏览器，也没有修改用户profile。
- 回放页面JavaScript语法、静态运行时/哈希检查及真实记录schema验证均通过；本机HTTP GET/HEAD、固定资源、真实记录哈希、路径穿越拒绝及POST不具控制能力均通过，见同目录Node日志与 `http-probe-run-002.json`。
- 因无安全可用的独立浏览器profile，中文排版、轨迹/速度Canvas的最终截图和页面console状态未完成。不得将HTTP/Node检查写成视觉验收。
