# n8n-docgen

Turn an exported n8n workflow (`.json`) into a clean Markdown document with a flow diagram, step list, credentials list, and warnings.

n8n workflows are hard to review as raw JSON. This tool gives you a readable page you can commit next to your workflow, share with a teammate, or paste into a wiki.

## Features

- **Overview**: node count, triggers, node types used, credentials, active status
- **Flow diagram**: a Mermaid chart that GitHub renders automatically
- **Step-by-step list** in the order the workflow runs, with notes and key settings
- **Warnings** for disconnected nodes, disabled nodes, and hardcoded secrets
- **Safe by design**: secret values are never printed, only the parameter name is flagged
- **No dependencies**: pure Python standard library

## Setup

You need Python 3.8 or newer.

```bash
git clone https://github.com/vinuthan01/n8n-docgen.git
cd n8n-docgen
```

## Usage

1. In n8n, open your workflow, click the **three dots menu**, then **Download**. You get a `.json` file.
2. Run:

```bash
python n8n_docgen.py my-workflow.json -o MY_WORKFLOW.md
```

Leave out `-o` to print to the terminal. You can pass several files at once.

## Demo

Try it on the included example:

```bash
python n8n_docgen.py examples/daily-news-digest.json
```

The full output is in [`examples/daily-news-digest.md`](examples/daily-news-digest.md).

<!-- Add a screenshot here after you run it:
![Example output](docs/screenshot.png) -->

## Run the tests

```bash
python -m unittest discover -s tests -v
```

## Project layout

```
n8n_docgen.py        the tool
tests/               unit tests
examples/            sample workflow and its generated doc
```

## Limitations

- Reads standard n8n exports; it does not talk to a running n8n server.
- Parameter summaries show only simple top-level values.

## License

MIT. See [LICENSE](LICENSE).
