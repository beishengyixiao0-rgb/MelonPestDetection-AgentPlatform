<template>
  <div class="markdown-message" v-html="renderedContent" />
</template>

<script setup>
import MarkdownIt from 'markdown-it'
import { computed } from 'vue'

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
})

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: true,
})

const defaultLinkOpen = markdown.renderer.rules.link_open
  || ((tokens, index, options, env, renderer) => renderer.renderToken(tokens, index, options))

markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, index, options, env, renderer)
}

const renderedContent = computed(() => markdown.render(props.content || ''))
</script>

<style scoped>
.markdown-message {
  min-width: 0;
  overflow-wrap: anywhere;
  color: inherit;
  font-size: 14px;
  line-height: 1.75;
}

.markdown-message :deep(> :first-child) { margin-top: 0; }
.markdown-message :deep(> :last-child) { margin-bottom: 0; }
.markdown-message :deep(p) { margin: 0 0 10px; }
.markdown-message :deep(h1),
.markdown-message :deep(h2),
.markdown-message :deep(h3),
.markdown-message :deep(h4) {
  margin: 18px 0 8px;
  color: #1f2937;
  line-height: 1.4;
}
.markdown-message :deep(h1) { font-size: 20px; }
.markdown-message :deep(h2) { font-size: 18px; }
.markdown-message :deep(h3) { font-size: 16px; }
.markdown-message :deep(h4) { font-size: 14px; }
.markdown-message :deep(ul),
.markdown-message :deep(ol) { margin: 8px 0 12px; padding-left: 22px; }
.markdown-message :deep(li) { margin: 4px 0; }
.markdown-message :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 12px;
  border-left: 3px solid #86c99d;
  border-radius: 0 8px 8px 0;
  background: #f3faf5;
  color: #4b6354;
}
.markdown-message :deep(code) {
  padding: 2px 5px;
  border-radius: 5px;
  background: #eef2ef;
  color: #166534;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9em;
}
.markdown-message :deep(pre) {
  max-width: 100%;
  margin: 12px 0;
  padding: 13px 15px;
  overflow-x: auto;
  border-radius: 10px;
  background: #17231c;
  color: #e8f5ec;
}
.markdown-message :deep(pre code) { padding: 0; background: transparent; color: inherit; }
.markdown-message :deep(a) { color: #15803d; text-decoration: underline; text-underline-offset: 3px; }
.markdown-message :deep(hr) { margin: 16px 0; border: 0; border-top: 1px solid #e2e8e4; }
.markdown-message :deep(table) {
  width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
  font-size: 13px;
}
.markdown-message :deep(th),
.markdown-message :deep(td) { padding: 8px 10px; border: 1px solid #dfe7e1; text-align: left; }
.markdown-message :deep(th) { background: #f1f7f3; color: #274532; font-weight: 700; }
.markdown-message :deep(img) { max-width: 100%; border-radius: 10px; }

@media (max-width: 640px) {
  .markdown-message { font-size: 13px; line-height: 1.7; }
  .markdown-message :deep(table) { display: block; overflow-x: auto; }
}
</style>
