import { defineNavbarConfig } from "vuepress-theme-plume"

export default defineNavbarConfig([
  { text: "指南", link: "/guide/" },
  { text: "核心概念", link: "/concepts/" },
  { text: "扩展开发", link: "/extensions/" },
  { text: "API 参考", link: "/api/" },
  { text: "示例", link: "/examples/" },
  {
    text: "GitHub",
    link: "https://github.com/GEYUANwuqi/Butter-Bot",
    icon: "mdi:github",
  },
])
