import { viteBundler } from "@vuepress/bundler-vite"
import { defineUserConfig } from "vuepress"
import { plumeTheme } from "vuepress-theme-plume"

export default defineUserConfig({
  lang: "zh-CN",
  title: "Butter-Bot",
  description: "面向异步事件源与处理器的 Python 机器人框架",
  base: "/",
  pagePatterns: ["**/*.md", "!review/**"],
  head: [
    ["meta", { name: "theme-color", content: "#3c7f72" }],
    ["meta", { name: "application-name", content: "Butter-Bot 文档" }],
  ],
  bundler: viteBundler(),
  theme: plumeTheme({
    autoFrontmatter: false,
    editLink: true,
    lastUpdated: {
      formatOptions: {
        dateStyle: "medium",
        timeStyle: "short",
      },
    },
    search: {
      provider: "local",
    },
    copyCode: true,
    markdown: {
      mermaid: true,
    },
    plugins: {
      git: true,
    },
  }),
})
