import { defineCollections } from "vuepress-theme-plume"

export default defineCollections([
  {
    type: "doc",
    dir: "guide",
    title: "使用指南",
    sidebar: [
      { text: "使用指南", link: "/guide/" },
      "introduction",
      "installation",
      "quick-start",
      "project-structure",
      "lifecycle",
      "cli",
    ],
  },
  {
    type: "doc",
    dir: "concepts",
    title: "核心概念",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "features",
    title: "功能指南",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "configuration",
    title: "配置参考",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "extensions",
    title: "扩展开发",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "api",
    title: "API 参考",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "examples",
    title: "示例与最佳实践",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "troubleshooting",
    title: "故障排除",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "architecture",
    title: "项目架构",
    sidebar: "auto",
  },
  {
    type: "doc",
    dir: "contributing",
    title: "贡献指南",
    sidebar: "auto",
  },
])
