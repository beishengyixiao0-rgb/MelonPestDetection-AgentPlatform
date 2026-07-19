// 轻量级界面文案字典。当前不增加第三方依赖，后续页面可继续复用 t 函数扩展键值。
const messages = {
  zh: {
    'language.zh': '中文',
    'language.en': 'EN',
    'language.changed': '已切换为中文',
    'language.failed': '语言切换失败',
    'user.profile': '个人中心',
    'user.logout': '退出登录',
    'user.logoutConfirm': '确定要退出登录吗？',
    'common.tip': '提示',
    'common.confirm': '确定',
    'common.cancel': '取消',
    'knowledge.rebuildIndex': '重建知识库索引',
    'knowledge.rebuildConfirm': '将重新解析知识库文件并调用 Embedding 服务生成向量索引，期间知识库检索可能暂时不可用。是否继续？',
    'knowledge.rebuildSuccess': '知识库索引重建完成',
    'nav.chat': '智能对话',
    'nav.detection': '检测工作台',
    'nav.training': '模型训练',
    'nav.history': '历史记录',
    'nav.dashboard': '数据看板',
  },
  en: {
    'language.zh': 'Chinese',
    'language.en': 'EN',
    'language.changed': 'Language changed to English',
    'language.failed': 'Unable to change language',
    'user.profile': 'Profile',
    'user.logout': 'Sign out',
    'user.logoutConfirm': 'Sign out of this account?',
    'common.tip': 'Notice',
    'common.confirm': 'Confirm',
    'common.cancel': 'Cancel',
    'knowledge.rebuildIndex': 'Rebuild Knowledge Index',
    'knowledge.rebuildConfirm': 'This will reprocess knowledge base files and generate vector embeddings. Knowledge retrieval may be temporarily unavailable. Continue?',
    'knowledge.rebuildSuccess': 'Knowledge base index rebuilt',
    'nav.chat': 'Chat',
    'nav.detection': 'Detection',
    'nav.training': 'Training',
    'nav.history': 'History',
    'nav.dashboard': 'Dashboard',
  },
}

// 按当前语言读取文案；缺失时回退中文，避免界面直接显示翻译键。
export function t(key, locale = 'zh') {
  return messages[locale]?.[key] || messages.zh[key] || key
}
