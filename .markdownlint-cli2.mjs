export default {
  config: {
    MD013: false,
    MD024: { siblings_only: true },
    MD025: false,
    MD033: false,
    MD041: false,
  },
  globs: ["README.md", "docs/**/*.md"],
  ignores: ["docs/.vuepress/**", "docs/review/**"],
}
