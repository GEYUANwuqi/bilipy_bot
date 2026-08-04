import { existsSync, readFileSync, readdirSync } from "node:fs"
import { extname, join, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const projectRoot = resolve(fileURLToPath(new URL("..", import.meta.url)))
const outputRoot = join(projectRoot, "docs", ".vuepress", "dist")
const siteConfigPath = join(projectRoot, "docs", ".vuepress", "config.ts")

if (!existsSync(outputRoot)) {
  console.error("文档构建产物不存在，请先运行 npm run docs:build")
  process.exit(1)
}

const siteConfig = readFileSync(siteConfigPath, "utf8")
const baseMatch = siteConfig.match(/\bbase:\s*["']([^"']+)["']/)
if (baseMatch === null) {
  console.error("无法从 docs/.vuepress/config.ts 读取站点 base")
  process.exit(1)
}
const siteBase = new URL(baseMatch[1], "https://docs.invalid").pathname

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? walk(path) : [path]
  })
}

function targetFile(pathname) {
  const cleanPath = decodeURI(pathname).replace(/^\/+/, "")
  if (cleanPath === "") return join(outputRoot, "index.html")
  if (pathname.endsWith("/")) return join(outputRoot, cleanPath, "index.html")
  if (extname(cleanPath) === "") return join(outputRoot, `${cleanPath}.html`)
  return join(outputRoot, cleanPath)
}

function stripSiteBase(pathname) {
  if (siteBase === "/") return pathname
  if (pathname === siteBase.slice(0, -1)) return "/"
  if (pathname.startsWith(siteBase)) return `/${pathname.slice(siteBase.length)}`
  return pathname
}

const failures = []
const htmlFiles = walk(outputRoot).filter((path) => path.endsWith(".html"))

for (const sourceFile of htmlFiles) {
  const html = readFileSync(sourceFile, "utf8")
  const hrefs = [...html.matchAll(/\shref="([^"]+)"/g)].map((match) => match[1])

  for (const href of hrefs) {
    if (
      href.startsWith("http://") ||
      href.startsWith("https://") ||
      href.startsWith("mailto:") ||
      href.startsWith("tel:") ||
      href.startsWith("javascript:")
    ) {
      continue
    }

    const sourceUrl = `https://docs.invalid/${relative(outputRoot, sourceFile).replaceAll("\\", "/")}`
    const url = new URL(href, sourceUrl)
    const localPathname = stripSiteBase(url.pathname)
    if (localPathname.startsWith("/assets/")) continue

    const destination = targetFile(localPathname)
    if (!existsSync(destination)) {
      failures.push(
        `${relative(outputRoot, sourceFile)} -> ${href}（目标文件不存在）`,
      )
      continue
    }

    if (url.hash) {
      const fragment = decodeURIComponent(url.hash.slice(1))
      const targetHtml = readFileSync(destination, "utf8")
      const escaped = fragment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      if (!new RegExp(`\\sid="${escaped}"(?:\\s|>)`).test(targetHtml)) {
        failures.push(
          `${relative(outputRoot, sourceFile)} -> ${href}（锚点不存在）`,
        )
      }
    }
  }
}

if (failures.length > 0) {
  console.error(`发现 ${failures.length} 个无效内部链接：`)
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`内部链接检查通过：${htmlFiles.length} 个 HTML 页面`)
