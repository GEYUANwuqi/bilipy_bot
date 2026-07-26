import { defineThemeConfig } from "vuepress-theme-plume"

import collections from "./collections.js"
import navbar from "./navbar.js"

export default defineThemeConfig({
  navbar,
  collections,
  docsRepo: "https://github.com/GEYUANwuqi/Butter-Bot",
  docsBranch: "dev_main",
  docsDir: "docs",
  footer: {
    message: "文档内容以当前公开 API、测试与示例为准。",
    copyright: "GPL-3.0",
  },
  appearance: true,
  social: [
    {
      icon: "github",
      link: "https://github.com/GEYUANwuqi/Butter-Bot",
    },
  ],
})
