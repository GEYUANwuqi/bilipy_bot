import { defineNavbarConfig } from "vuepress-theme-plume"

export default defineNavbarConfig([
  { text: "指南", link: "/guide/" },
  { text: "核心概念", link: "/concepts/" },
  { text: "扩展开发", link: "/extensions/" },
  { text: "API 参考", link: "/api/" },
  { text: "示例", link: "/examples/" },
  {
    text: "更多",
    items: [
      { text: "功能指南", link: "/features/" },
      { text: "配置参考", link: "/configuration/" },
      { text: "故障排除", link: "/troubleshooting/" },
      { text: "项目架构", link: "/architecture/" },
    ],
  },
  {
    text: "GitHub",
    link: "https://github.com/GEYUANwuqi/Butter-Bot",
    icon: "mdi:github",
  },
])
