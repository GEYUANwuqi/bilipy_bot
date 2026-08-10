import { defineNavbarConfig } from "vuepress-theme-plume"

export default defineNavbarConfig([
  { text: "入门", link: "/guide/" },
  { text: "功能指南", link: "/features/" },
  { text: "扩展开发", link: "/extensions/" },
  { text: "框架开发", link: "/architecture/" },
  { text: "API 参考", link: "/api/" },
  {
    text: "GitHub",
    link: "https://github.com/GEYUANwuqi/Butter-Bot",
    icon: "mdi:github",
  },
])
