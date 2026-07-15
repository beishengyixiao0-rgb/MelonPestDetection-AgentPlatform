/**
 * SSE (Server-Sent Events) 流式处理工具
 *
 * 用于 AI Agent 对话流式渲染。
 *
 * 使用示例：
 *
 * const stop = streamChat(
 *   "/api/chat/stream",
 *   { message: "你好" },
 *   {
 *     onMessage: (chunk) => {
 *       content += chunk.content
 *     },
 *     onDone: () => {
 *       console.log("完成")
 *     },
 *     onError: (err) => {
 *       console.error(err)
 *     }
 *   }
 * )
 *
 * stop() // 中断连接
 */

/**
 * 发起 SSE 流式请求
 *
 * @param {string} url
 * @param {Object} body
 * @param {Object} callbacks
 * @param {Function} callbacks.onMessage
 * @param {Function} callbacks.onDone
 * @param {Function} callbacks.onError
 *
 * @returns {Function} stop
 */
export function streamChat(url, body, callbacks = {}) {
  const { onMessage, onDone, onError } = callbacks;

  const token = localStorage.getItem("rsod_token");

  const controller = new AbortController();

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {}),
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      // SSE 缓冲区
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          if (buffer.trim()) {
            processSSEMessage(buffer, onMessage);
          }

          onDone?.();
          break;
        }

        buffer += decoder.decode(value, {
          stream: true,
        });

        // SSE 消息以空行分隔
        const messages = buffer.split("\n\n");

        // 最后一段可能不完整
        buffer = messages.pop() || "";

        for (const message of messages) {
          if (!message.trim()) continue;

          const shouldStop = processSSEMessage(message, onMessage);

          if (shouldStop) {
            onDone?.();
            return;
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError?.(err);
      }
    });

  return () => controller.abort();
}

/**
 * 处理单条 SSE 消息
 *
 * @param {string} message
 * @param {Function} onMessage
 *
 * @returns {boolean}
 */
function processSSEMessage(message, onMessage) {
  const lines = message.split("\n");

  for (const line of lines) {
    if (!line.startsWith("data: ")) {
      continue;
    }

    const data = line.slice(6);

    if (data === "[DONE]") {
      return true;
    }

    try {
      const parsed = JSON.parse(data);

      onMessage?.(parsed);
    } catch {
      console.warn("[SSE] JSON parse failed:", data.length);

      onMessage?.({
        type: "text_chunk",
        content: data,
      });
    }
  }

  return false;
}
