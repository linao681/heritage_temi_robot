(() => {
  const ALLOWED_SOURCE_STATUSES = new Set(['PASS', 'PASS_WITH_RISK', 'FAIL']);
  const SHA256_RE = /^[a-f0-9]{64}$/i;

  async function sha256Hex(bytes) {
    if (globalThis.crypto && globalThis.crypto.subtle) {
      const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
      return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('');
    }
    if (typeof require === 'function') {
      return require('node:crypto').createHash('sha256').update(Buffer.from(bytes)).digest('hex');
    }
    throw new Error('当前浏览器不支持 SHA256 校验');
  }

  function parseChecksum(text, jsonFileName) {
    const match = /^([a-f0-9]{64})  (.+)$/im.exec(String(text).trim());
    if (!match || match[2] !== jsonFileName) throw new Error('回放文件校验和清单无效');
    return match[1].toLowerCase();
  }

  async function verifyRecordingFiles(jsonText, checksumText, jsonFileName) {
    const expected = parseChecksum(checksumText, jsonFileName);
    const jsonBytes = new TextEncoder().encode(jsonText);
    if (await sha256Hex(jsonBytes) !== expected) throw new Error('回放 JSON SHA256 不匹配');
    const recording = JSON.parse(jsonText);
    await validateRecording(recording);
    return recording;
  }

  async function validateRecording(recording) {
    if (!recording || recording.schema_version !== 1 || recording.mode !== 'RECORDED_ROS2') {
      throw new Error('记录模式或版本无效');
    }
    if (!recording.run_id || !recording.source || !ALLOWED_SOURCE_STATUSES.has(recording.source.status)) {
      throw new Error('实验来源无效');
    }
    if (!SHA256_RE.test(recording.source.archive_sha256 || '') ||
        !SHA256_RE.test(recording.source.manifest_sha256 || '') ||
        !recording.integrity || recording.integrity.source_archive_sha256 !== recording.source.archive_sha256 ||
        recording.integrity.source_manifest_sha256 !== recording.source.manifest_sha256) {
      throw new Error('来源哈希缺失或不一致');
    }
    const manifestBytes = new TextEncoder().encode(recording.source.manifest_json_raw || '');
    if (await sha256Hex(manifestBytes) !== recording.source.manifest_sha256) {
      throw new Error('来源 manifest SHA256 不匹配');
    }
    const manifest = JSON.parse(recording.source.manifest_json_raw);
    if (manifest.run_id !== recording.run_id || manifest.status !== recording.source.status ||
        manifest.archive_sha256 !== recording.source.archive_sha256) {
      throw new Error('来源 manifest 与回放数据不匹配');
    }
    if (!Array.isArray(recording.events) || !Array.isArray(recording.rgb_frames) ||
        !Array.isArray(recording.depth_frames) || recording.controls_available !== false) {
      throw new Error('回放数据结构无效或包含控制能力');
    }
    const eventIds = new Set();
    let previousStamp = -1;
    for (const event of recording.events) {
      if (!event || !event.event_id || eventIds.has(event.event_id) ||
          !Number.isSafeInteger(event.stamp_ns) || event.stamp_ns < 0 ||
          !Number.isSafeInteger(event.relative_time_ns) || event.relative_time_ns < 0 ||
          event.stamp_ns < previousStamp) {
        throw new Error('事件时间线无效');
      }
      previousStamp = event.stamp_ns;
      eventIds.add(event.event_id);
    }
    const verifiedFiles = new Set((recording.source.verified_source_files || []).map(file => file.path));
    for (const frame of recording.rgb_frames) {
      if (!verifiedFiles.has(frame.path) || !SHA256_RE.test(frame.sha256 || '') ||
          !/^data:image\/(png|jpeg);base64,/.test(frame.data_url || '')) {
        throw new Error('RGB 帧来源无效');
      }
      const encoded = frame.data_url.slice(frame.data_url.indexOf(',') + 1);
      const imageBytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
      if (await sha256Hex(imageBytes) !== frame.sha256) throw new Error('RGB 帧 SHA256 不匹配');
    }
    for (const frame of recording.depth_frames) {
      if (!verifiedFiles.has(frame.path) || !SHA256_RE.test(frame.sha256 || '')) {
        throw new Error('Depth 帧来源无效');
      }
    }
    return true;
  }

  function nearestFrame(frames, stampNs, toleranceNs = 250_000_000) {
    let best = null;
    let difference = Infinity;
    for (const frame of frames || []) {
      const current = Math.abs(frame.stamp_ns - stampNs);
      if (current < difference) {
        best = frame;
        difference = current;
      }
    }
    return difference <= toleranceNs ? best : null;
  }

  function boxesForEvent(event) {
    const data = event && event.data;
    if (!data) return [];
    const items = Array.isArray(data.tracks) ? data.tracks : Array.isArray(data.detections) ? data.detections : [];
    return items.filter(item => Array.isArray(item.bbox) && item.bbox.length === 4)
      .map(item => ({bbox: item.bbox, label: item.track_id || `${Math.round((item.confidence || 0) * 100)}%`}));
  }

  function initPage() {
    const input = document.getElementById('recording-file');
    const loadState = document.getElementById('load-state');
    const mode = document.getElementById('mode-badge');
    const meta = document.getElementById('recording-meta');
    const canvas = document.getElementById('frame-canvas');
    const context = canvas.getContext('2d');
    const slider = document.getElementById('timeline');
    const timeLabel = document.getElementById('time-label');
    const eventsList = document.getElementById('events');
    const speed = document.getElementById('playback-speed');
    const playButton = document.getElementById('play-pause');
    const image = new Image();
    let recording = null;
    let firstStamp = 0;
    let durationNs = 0;
    let playing = false;
    let lastTick = null;
    let currentImageData = null;

    function currentStamp() {
      return firstStamp + Math.round(Number(slider.value) * 1_000_000);
    }

    function drawTrajectory(stamp) {
      const plot = document.getElementById('trajectory-canvas');
      const ctx = plot.getContext('2d');
      const padding = 30;
      ctx.clearRect(0, 0, plot.width, plot.height);
      ctx.fillStyle = '#24211d';
      ctx.fillRect(0, 0, plot.width, plot.height);
      const robot = recording.robot_pose_series.filter(item => item.stamp_ns <= stamp);
      const visitors = recording.visitor_pose_series.filter(item => item.stamp_ns <= stamp);
      const all = [...recording.robot_pose_series, ...recording.visitor_pose_series];
      if (!all.length) {
        ctx.fillStyle = '#eee7da';
        ctx.font = '16px sans-serif';
        ctx.fillText('本轮没有可回放的位置样本', padding, padding);
        return;
      }
      const xs = all.map(item => item.x), zs = all.map(item => item.z);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minZ = Math.min(...zs), maxZ = Math.max(...zs);
      const scaleX = (plot.width - 2 * padding) / Math.max(0.1, maxX - minX);
      const scaleZ = (plot.height - 2 * padding) / Math.max(0.1, maxZ - minZ);
      const scale = Math.min(scaleX, scaleZ);
      const centerX = plot.width / 2, centerY = plot.height / 2;
      const point = item => ({
        x: centerX + (item.x - (minX + maxX) / 2) * scale,
        y: centerY - (item.z - (minZ + maxZ) / 2) * scale,
      });
      function drawPath(items, color, source, labelY) {
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        let previous = null;
        for (const item of items) {
          const current = point(item);
          if (!previous || item.stamp_ns - previous.stamp_ns > 1_000_000_000) {
            ctx.moveTo(current.x, current.y);
          } else {
            ctx.lineTo(current.x, current.y);
          }
          previous = item;
        }
        ctx.stroke();
        const last = items[items.length - 1];
        if (last) {
          const current = point(last);
          ctx.beginPath();
          ctx.arc(current.x, current.y, 4, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillText(source, padding, labelY);
      }
      drawPath(robot, '#64d7a2', 'Robot · ROS TF', 18);
      const visitorGroups = new Map();
      for (const item of visitors) {
        if (!visitorGroups.has(item.id)) visitorGroups.set(item.id, []);
        visitorGroups.get(item.id).push(item);
      }
      const colors = ['#f2a65a', '#80b8ff', '#e583c5', '#d4ca6b', '#8cd6d1'];
      let index = 0;
      for (const [id, items] of visitorGroups) {
        drawPath(items, colors[index % colors.length], `Gazebo truth · ${id}`, 38 + index * 18);
        index += 1;
      }
      ctx.fillStyle = '#c9c0b4';
      ctx.fillText('Hall display coordinates (m)', padding, plot.height - 10);
    }

    function drawSpeed(stamp) {
      const plot = document.getElementById('speed-canvas');
      const ctx = plot.getContext('2d');
      const padding = 34;
      ctx.clearRect(0, 0, plot.width, plot.height);
      ctx.fillStyle = '#24211d';
      ctx.fillRect(0, 0, plot.width, plot.height);
      const items = recording.speed_series.filter(item => item.stamp_ns <= stamp);
      const start = firstStamp;
      const end = Math.max(start + 1, Number(slider.max) * 1_000_000 + firstStamp);
      const maxSpeed = Math.max(0.1, ...recording.speed_series.map(item => item.linear_speed_mps));
      const x = time => padding + (time - start) / (end - start) * (plot.width - 2 * padding);
      const y = value => plot.height - padding - value / maxSpeed * (plot.height - 2 * padding);
      ctx.strokeStyle = '#625b52';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padding, padding);
      ctx.lineTo(padding, plot.height - padding);
      ctx.lineTo(plot.width - padding, plot.height - padding);
      ctx.stroke();
      for (const [source, color] of [['cmd_vel', '#f2a65a'], ['odom', '#64d7a2']]) {
        const series = items.filter(item => item.source === source);
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        let previous = null;
        for (const item of series) {
          const currentX = x(item.stamp_ns), currentY = y(item.linear_speed_mps);
          if (!previous || item.stamp_ns - previous.stamp_ns > 1_000_000_000) {
            ctx.moveTo(currentX, currentY);
          } else {
            ctx.lineTo(currentX, currentY);
          }
          previous = item;
        }
        ctx.stroke();
        ctx.fillText(source === 'cmd_vel' ? 'cmd_vel · 指令' : 'odom · 实测',
          padding + (source === 'cmd_vel' ? 4 : 170), 18);
      }
      ctx.fillStyle = '#c9c0b4';
      ctx.fillText(`线速度 (m/s) · 记录样本截至 ${((stamp - firstStamp) / 1e9).toFixed(1)} s`,
        padding, plot.height - 8);
    }

    function drawFrame() {
      const stamp = currentStamp();
      const frame = nearestFrame(recording.rgb_frames, stamp);
      const nearestEvent = recording.events.reduce((best, event) =>
        !best || Math.abs(event.stamp_ns - stamp) < Math.abs(best.stamp_ns - stamp) ? event : best, null);
      timeLabel.textContent = `${((stamp - firstStamp) / 1e9).toFixed(2)} s / ${(durationNs / 1e9).toFixed(2)} s`;
      drawTrajectory(stamp);
      drawSpeed(stamp);
      context.clearRect(0, 0, canvas.width, canvas.height);
      if (!frame) {
        context.fillStyle = '#eee7da';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = '#51483d';
        context.font = '18px sans-serif';
        context.fillText('此时刻没有保存的 RGB 帧', 24, 40);
        currentImageData = null;
        return;
      }
      if (currentImageData !== frame.data_url) {
        currentImageData = frame.data_url;
        image.onload = drawFrame;
        image.src = frame.data_url;
        return;
      }
      canvas.width = frame.width;
      canvas.height = frame.height;
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      if (nearestEvent && Math.abs(nearestEvent.stamp_ns - frame.stamp_ns) <= 250_000_000) {
        context.lineWidth = Math.max(1, canvas.width / 240);
        context.font = `${Math.max(10, canvas.width / 32)}px sans-serif`;
        for (const box of boxesForEvent(nearestEvent)) {
          const [x1, y1, x2, y2] = box.bbox;
          if (![x1, y1, x2, y2].every(Number.isFinite) || Math.max(x1, y1, x2, y2) > 1.5) continue;
          const x = x1 * canvas.width, y = y1 * canvas.height;
          const w = (x2 - x1) * canvas.width, h = (y2 - y1) * canvas.height;
          context.strokeStyle = '#21d07a';
          context.strokeRect(x, y, w, h);
          context.fillStyle = '#21d07a';
          context.fillText(box.label, x, Math.max(12, y - 3));
        }
      }
    }

    function seekEvent(event) {
      slider.value = String(Math.max(0, Math.min(Number(slider.max),
        Math.round((event.stamp_ns - firstStamp) / 1_000_000))));
      drawFrame();
    }

    function populateEvents() {
      eventsList.replaceChildren();
      for (const event of recording.events.slice(0, 500)) {
        const button = document.createElement('button');
        const payload = event.data || {};
        let label;
        if (event.type === 'team_observation') {
          label = `视觉团队 ${payload.observation_state || '状态'} · ${payload.observed_count ?? '—'}/${payload.expected_count ?? '—'}`;
        } else if (event.type === 'gazebo_team_truth') {
          label = `Gazebo真值 ${payload.state || '状态'} · ${payload.count ?? '—'} 人 · 落后 ${payload.lag_m ?? '—'} m`;
        } else if (event.type === 'tour_state') {
          label = `导览 ${payload.state || '状态'} · ${payload.reason || ''}`;
        } else if (event.type === 'safety_state') {
          label = `安全 ${payload.state || '状态'} · ${payload.reason || ''}`;
        } else if (event.type === 'cmd_vel' || event.type === 'odom') {
          label = `${event.type} · ${payload.linear_speed_mps?.toFixed(2) ?? '—'} m/s`;
        } else if (event.type.endsWith('_detection')) {
          label = `${event.type} · ${payload.people_count ?? payload.detections?.length ?? 0} 人`;
        } else {
          label = `匿名轨迹 · ${(payload.tracks || []).length} 人`;
        }
        button.textContent = `${((event.stamp_ns - firstStamp) / 1e9).toFixed(2)} s  ${label}`;
        button.addEventListener('click', () => seekEvent(event));
        eventsList.appendChild(button);
      }
      if (recording.events.length > 500) {
        const note = document.createElement('p');
        note.textContent = `仅显示前500/${recording.events.length}条事件，原始回放不变。`;
        eventsList.appendChild(note);
      }
    }

    function loadRecording(value) {
      recording = value;
      const stamps = recording.events.map(event => event.stamp_ns)
        .concat(recording.rgb_frames.map(frame => frame.stamp_ns))
        .filter(Number.isSafeInteger);
      firstStamp = stamps.length ? Math.min(...stamps) : 0;
      const lastStamp = stamps.length ? Math.max(...stamps) : firstStamp;
      durationNs = Math.max(0, lastStamp - firstStamp);
      slider.max = String(Math.max(1, Math.ceil(durationNs / 1_000_000)));
      slider.value = '0';
      meta.textContent = `实验 ${recording.run_id} · 来源状态 ${recording.source.status} · 归档 SHA256 ${recording.source.archive_sha256}`;
      document.getElementById('trajectory-note').textContent =
        recording.robot_pose_series.length || recording.visitor_pose_series.length
          ? `机器人 ROS TF ${recording.robot_pose_series.length} 点 · 游客 Gazebo ModelStates 真值 ${recording.visitor_pose_series.length} 点`
          : '本轮未记录世界坐标位置；匿名框只在匹配图像上显示，不拼接成物理轨迹。';
      document.getElementById('speed-note').textContent = recording.speed_series.length
        ? `本轮保存 ${recording.speed_series.filter(item => item.source === 'cmd_vel').length} 条 cmd_vel 指令与 ${recording.speed_series.filter(item => item.source === 'odom').length} 条 odom 速度观测。`
        : `本轮没有速度曲线数据；不插值、不使用仿真真值补造。`;
      document.getElementById('frame-caption').textContent = recording.rgb_frames.length
        ? '检测框仅叠加于同一时间附近的已保存 RGB 图像。'
        : '本轮没有保存 RGB 图像；仅回放记录中的匿名检测框坐标，不伪造图像叠加。';
      populateEvents();
      mode.textContent = 'RECORDED_ROS2 · 来源与文件哈希已校验';
      mode.className = 'mode valid';
      loadState.textContent = '记录已加载。播放、暂停、倍速与事件定位只改变本地时间轴。';
      drawFrame();
    }

    input.addEventListener('change', async () => {
      playing = false;
      playButton.textContent = '播放';
      try {
        const files = [...input.files];
        const jsonFile = files.find(file => file.name.endsWith('.json'));
        const checksumFile = files.find(file => file.name.endsWith('.sha256'));
        if (!jsonFile || !checksumFile) throw new Error('请同时选择 replay.json 和 replay.json.sha256');
        const [jsonText, checksumText] = await Promise.all([jsonFile.text(), checksumFile.text()]);
        loadRecording(await verifyRecordingFiles(jsonText, checksumText, jsonFile.name));
      } catch (error) {
        recording = null;
        mode.textContent = 'RECORDED_ROS2 · 校验失败';
        mode.className = 'mode invalid';
        loadState.textContent = error.message || '文件无效，拒绝按真实记录回放。';
      }
    });

    if (location.protocol === 'http:' && location.hostname === '127.0.0.1') {
      Promise.all([
        fetch('/recording/replay.json', {cache: 'no-store'}),
        fetch('/recording/replay.json.sha256', {cache: 'no-store'})
      ]).then(async ([jsonResponse, checksumResponse]) => {
        if (!jsonResponse.ok || !checksumResponse.ok) throw new Error('本地回放文件读取失败');
        const [jsonText, checksumText] = await Promise.all([
          jsonResponse.text(), checksumResponse.text()
        ]);
        loadRecording(await verifyRecordingFiles(jsonText, checksumText, 'replay.json'));
      }).catch(error => {
        mode.textContent = 'RECORDED_ROS2 · 校验失败';
        mode.className = 'mode invalid';
        loadState.textContent = error.message || '本地记录无效，已拒绝载入。';
      });
    }

    slider.addEventListener('input', () => recording && drawFrame());
    playButton.addEventListener('click', () => {
      if (!recording) return;
      playing = !playing;
      lastTick = null;
      playButton.textContent = playing ? '暂停' : '继续';
      if (playing) requestAnimationFrame(tick);
    });
    function tick(now) {
      if (!playing || !recording) return;
      if (lastTick !== null) {
        const elapsedMs = (now - lastTick) * Number(speed.value);
        slider.value = String(Math.min(Number(slider.max), Number(slider.value) + elapsedMs));
        drawFrame();
      }
      lastTick = now;
      if (Number(slider.value) >= Number(slider.max)) {
        playing = false;
        playButton.textContent = '继续';
        lastTick = null;
        return;
      }
      requestAnimationFrame(tick);
    }
  }

  const api = {parseChecksum, verifyRecordingFiles, validateRecording, nearestFrame, boxesForEvent};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document !== 'undefined') initPage();
})();
