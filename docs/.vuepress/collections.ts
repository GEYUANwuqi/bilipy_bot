import { defineCollections } from "vuepress-theme-plume"

export default defineCollections([
  {
    type: "doc",
    dir: "guide",
    title: "入门",
    sidebar: [
      { text: "入门", link: "/guide/" },
      "introduction",
      "installation",
      "quick-start",
      "project-structure",
      "basic-example",
      "best-practices",
    ],
  },
  {
    type: "doc",
    dir: "features",
    title: "功能指南",
    sidebar: [
      { text: "功能指南", link: "/features/" },
      "cli",
      { text: "配置", link: "/features/configuration/" },
      "runtime-modes",
      "subscriptions",
      {
        text: "事件源",
        collapsed: false,
        items: [
          { text: "事件源介绍", link: "/features/sources/" },
          { text: "NapCat", link: "/features/sources/napcat.html" },
          { text: "Bilibili", link: "/features/sources/bilibili.html" },
          {
            text: "运行期事件源管理",
            link: "/features/sources/runtime-management.html",
          },
        ],
      },
      { text: "故障排除", link: "/features/troubleshooting/" },
    ],
  },
  {
    type: "doc",
    dir: "extensions",
    title: "扩展开发",
    sidebar: [
      { text: "扩展开发概览", link: "/extensions/" },
      "custom-source",
      "custom-api",
      "custom-data-types",
      "custom-filter",
      "plugin-development",
      "testing",
    ],
  },
  {
    type: "doc",
    dir: "architecture",
    title: "框架开发",
    sidebar: [
      { text: "框架开发", link: "/architecture/" },
      "core-concepts",
      "lifecycle",
      "project-architecture",
      {
        text: "事件系统",
        collapsed: false,
        items: [
          { text: "Event", link: "/architecture/event-system/event.html" },
          {
            text: "EventBus",
            link: "/architecture/event-system/event-bus.html",
          },
          {
            text: "订阅系统",
            link: "/architecture/event-system/subscriptions.html",
          },
          {
            text: "过滤与匹配机制",
            link: "/architecture/event-system/filtering.html",
          },
        ],
      },
      {
        text: "事件源系统",
        collapsed: false,
        items: [
          {
            text: "Source 生命周期",
            link: "/architecture/source-system/lifecycle.html",
          },
          {
            text: "SourceManager",
            link: "/architecture/source-system/source-manager.html",
          },
        ],
      },
      {
        text: "API 系统",
        collapsed: false,
        items: [
          {
            text: "BaseApi",
            link: "/architecture/api-system/base-api.html",
          },
          {
            text: "APIContext",
            link: "/architecture/api-system/api-context.html",
          },
        ],
      },
      "conventions",
    ],
  },
  {
    type: "doc",
    dir: "api",
    title: "API 参考",
    sidebar: [
      { text: "API 参考", link: "/api/" },
      "bot-app",
      "event",
      "event-bus",
      "subscriber",
      "subscribe",
      {
        text: "Filter",
        collapsed: false,
        items: [
          { text: "BaseFilter", link: "/api/filter/base-filter.html" },
          {
            text: "CombinedFilter",
            link: "/api/filter/combined-filter.html",
          },
        ],
      },
      {
        text: "Source",
        collapsed: false,
        items: [
          { text: "BaseSource", link: "/api/source/base-source.html" },
          {
            text: "SourceManager",
            link: "/api/source/source-manager.html",
          },
        ],
      },
      {
        text: "API",
        collapsed: false,
        items: [
          { text: "BaseApi", link: "/api/api/base-api.html" },
          { text: "APIContext", link: "/api/api/api-context.html" },
        ],
      },
      "data-types",
      "config",
      "exceptions",
      "utilities",
    ],
  },
])
