# 3.1 非遗知识库与离线问答

五个主题、15 个问答意图，数据存于 `config/knowledge.yaml`。资料来自中国非物质文化遗产网，条目记录出处及核对日期；回答为资料的简明概括，尚未经过展厅工作人员审校。不是实际展品说明，也不是生成式大模型。

从项目根目录运行：

```bash
bash scripts/build_ros2.sh
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 run heritage_knowledge knowledge_qa '潮剧用什么语言'
ros2 run heritage_knowledge knowledge_qa '有什么特点' --exhibit exhibit_01 --level advanced
```

本机 ROS2 服务：

```bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=219
ros2 run heritage_knowledge knowledge_node
```

另一个加载同一工作空间、设置同一 Domain 的终端：

```bash
ros2 service call /heritage/knowledge/ask temi_interfaces/srv/AskHeritage '{question: "工夫茶用什么茶", level: basic}'
```

响应包含 `found`、`entry_id`、`answer`、`source_json`。主题或意图不明确、冲突以及未覆盖问题时拒答。别名和关键词须维护扩展；有限规则并不能理解所有自然语言或识别所有语义冲突，不是开放域问答准确率。增加条目时核对官方原始来源，补充测试、独立审校和版本。节点不控制运动或播报，不需要联网推理。

3.2 已接入 [导览 QA](tour_qa.md)，在 Mock 中验证播报、回答后继续路线及取消控制；真实 ASR/TTS 仍待设备验证。

## 本机验收

- 五个 ROS2 包完整构建成功（36.5 秒）。
- 新增 22 项测试，覆盖五个主题全部 15 个问答意图、未知问题拒答、跨展区冲突、分层及真实独立进程 Service 回环。
- 完整回归 **178 passed in 59.85s**。[测试日志](acceptance/knowledge/tests.log) · [JUnit](acceptance/knowledge/linux_junit.xml)。
- 实际 CLI 进阶问答返回潮州木雕早期历史及官方出处；询问潮绣价格时拒答，无来源返回。
