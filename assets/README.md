# Documentation visuals

- `hero.svg`: editable concept illustration; not an application screenshot.
- `architecture.svg`: source-grounded data flow, including the separation of extracted claims from factual retrieval.
- `pilot-results.png`: actual rubric pass counts and answering tokens from `artifacts/deepseek-pilot.json`. Its caption includes shared preprocessing cost and study limitations.

Rebuild from the repository root:

```bash
python3 docs/render_assets.py
```

The renderer uses Python's standard library and the optional development tool Matplotlib. Matplotlib is not required by the application or unit tests. SVG assets can also be edited directly in the renderer. Keep data captions and alt text consistent with the recorded study; do not substitute decorative or invented benchmark values.
