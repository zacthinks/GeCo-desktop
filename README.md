# 🦎 GeCo Desktop

**From documents to geometric coding—without writing Python.**

GeCo Desktop makes [Geometric Coder (GeCo)](https://github.com/zacthinks/GeCo) accessible through a desktop application. Prepare a collection of texts, explore different ways they relate to one another, develop codes through close reading and human judgment, and use computational models to help you apply and refine those codes across your corpus.

You can do all of this without writing Python or setting up a programming environment. GeCo Desktop helps you prepare a research project and then opens the full GeCo research workspace in your web browser, running locally on your computer.

**[Download and installation](#download-and-install) · [First-project guide](docs/getting-started.md) · [Learn more about GeCo](https://github.com/zacthinks/GeCo)**

## What is geometric coding?

Geometric coding begins with the idea that texts can be represented in different computational spaces, or **geometries**. A geometry gives us a way to think about relationships among observations: which texts are close together, which are far apart, and which similarities become visible from a particular perspective.

For example, one geometry might bring together texts that use similar words. Another might bring together texts with related meanings, even when they use different language. Neither is the single correct picture of the corpus. Different geometries can reveal different patterns, exceptions, and questions worth investigating.

GeCo connects these representations back to the original text. You can move from a map of your corpus to a particular passage, read it in context, make coding judgments, and return to the broader patterns. You can also use a **view**—a lower-dimensional projection of a geometry—to make some of those relationships visible on a map.

The point is not to let a computational model decide what your codes mean. **You define and refine the codes; geometries and learned models give you new ways to explore, test, and apply them.**

## Explore, Develop, Apply & Review

GeCo's three main workspaces support an iterative research process, not a one-way sequence.

### Explore — discover patterns and follow connections

Explore your corpus through different geometries and views. Follow nearby or distant observations, find unexpected cases, search for phrases or semantically related text, and use metadata to investigate subsets of your corpus.

Read observations in context, assign codes to texts or passages, and record interpretive memos. Changing geometries lets you revisit the same corpus from another perspective. In linked projects, GeCo also offers tools for comparing representations and exploring topics.

### Develop — teach models what your codes mean

As you make coding judgments, GeCo can learn from your examples. Train code-specific classifiers using different geometries, then ask the system to suggest observations that may be relevant, uncertain, or informative.

You can compare models, inspect disagreements, revise your judgments, and train again. This process of **active learning** keeps the researcher involved: your judgments inform the model, and the model helps direct your attention toward cases worth examining.

### Apply & Review — work across the corpus

When a classifier or committee has become useful, GeCo can generate coding proposals across observations you have not yet reviewed. Inspect the suggestions, examine their confidence, and accept, revise, or leave them undecided.

Model predictions remain distinct from your human coding decisions until you review and commit them. New findings may send you back to Explore or Develop to rethink a code or improve its models.

GeCo also includes dedicated spaces for **Codes** and **Memos**, so definitions and interpretation remain connected to the research as it evolves.

For the full GeCo workflow, see the [GeCo project](https://github.com/zacthinks/GeCo).

## How GeCo Desktop helps you get started

Geometric coding begins long before you open a map. A usable corpus may require importing files, identifying text and metadata, cleaning passages, restructuring observations, and choosing representations.

GeCo Desktop provides a guided preparation workbench for that process:

- **Bring in your materials.** Import CSV, Excel, JSONL, Parquet, text files, or supported PDF sources, including folders where applicable. Choose which fields contain text and which contain metadata.
- **Inspect before you change anything.** Browse sampled rows, try cleaning or restructuring operations, and compare **Before** and **After** previews before applying a step to the corpus.
- **Prepare your texts.** Use operations such as regex cleaning, named-pattern extraction, delimiter-based splitting, and other available text-processing tools. Applied steps are retained in your research project.
- **Choose representations.** Build word-count or TF-IDF representations, create SVD or UMAP views, or use supported language-model tools when their required resources are available.
- **Open GeCo.** Review the documents, text field, geometry, and optional view you want to start with. Create the linked coding workspace and open GeCo in your browser.

You do not have to complete every preparation operation. Start with what your corpus needs, and use GeCo to explore and develop your analysis.

GeCo Desktop can reopen your saved projects and reconnect to its managed browser sessions. Your project is a portable folder you can close, copy, and reopen on another computer, subject to the availability of its saved scientific environment and models.

## Download and install

**Current status: development preview.** Windows and macOS installers are built and automatically tested, but GeCo Desktop does **not yet have a published public release**. The builds below are for preview testing; the first full hands-on acceptance pass with real research data has not yet been completed.

<details>
<summary>Windows — preview installer</summary>

1. Open the [latest GeCo Desktop native-build workflow](https://github.com/zacthinks/GeCo-desktop/actions/workflows/native-build.yml).
2. Choose a **successful** run from the development branch and find its **Artifacts** section. You may need to sign in to GitHub.
3. Download `geco-desktop-windows`, extract the ZIP, and run `GeCoDesktop-Windows-Setup.exe` inside the extracted files.
4. Follow the installer. If you want to open `.gecod` project descriptors by double-clicking them, select the optional file-association setting.

The installer is currently a development build and may not be digitally signed. Only open builds you obtained from this repository and trust. Installation does not require you to install Python separately.

</details>

<details>
<summary>macOS — preview disk image</summary>

1. Open the [latest GeCo Desktop native-build workflow](https://github.com/zacthinks/GeCo-desktop/actions/workflows/native-build.yml).
2. Choose a **successful** run from the development branch. Under **Artifacts**, download `geco-desktop-macos` and extract the ZIP.
3. Open `GeCoDesktop-macOS.dmg` and copy **GeCo Desktop.app** to your Applications folder.
4. Open GeCo Desktop. This preview is unsigned, so macOS may require you to explicitly approve opening an application from an unidentified developer in **System Settings → Privacy & Security**. Do this only if you trust the downloaded build.

You do not need to install Python separately. The preview installer is currently built for the macOS architecture used by the project's CI runner; other Mac architectures have not yet been qualified.

</details>

The first time you create a project, GeCo Desktop may ask to install a compatible scientific environment. Additional processing models may require a download. These resources are shared outside your project folder and are not installed without your confirmation.

**[Create your first project →](docs/getting-started.md)**

## A few useful concepts

| Concept | Meaning |
| --- | --- |
| **Observation** | A unit of text you can examine or code, such as a document, row, or passage. |
| **Representation** | A computational representation of text; it may serve as a geometry, a view, or both. |
| **Geometry** | A representation used to examine distances, neighborhoods, and other relationships among observations. |
| **View** | A lower-dimensional projection of a geometry, often used to make relationships visible on a map. |
| **Code** | A researcher-defined concept, supported by descriptions, coding judgments, and evidence. |
| **Classifier** | A model trained to recognize a particular code from researcher-provided examples. |

GeCo is an exploratory research environment. Its representations, classifier suggestions, and maps help develop interpretations; they are not, by themselves, population estimates or substitutes for an appropriate inferential design.

## Beyond the Desktop

GeCo Desktop makes geometric coding accessible through a graphical interface, but **your project does not have to end there**.

Every GeCo Desktop project is also a [Text Analysis Lab (TeAL)](https://github.com/zacthinks/text-analysis-lab) project. TeAL preserves your imported data, prepared artifacts, computational representations, and the analytical history connecting them. GeCo adds the coding workspace and its researcher-defined judgments.

If you want to extend your work into a more specialized analysis, construct a larger data-science pipeline, or collaborate with someone who works programmatically, you can use TeAL's Python interface to continue from the same underlying project. The work you completed through the desktop interface does not have to be recreated from scratch.

Learn more about [**Text Analysis Lab (TeAL)**](https://github.com/zacthinks/text-analysis-lab), or explore [**GeCo**](https://github.com/zacthinks/GeCo) directly.

---

For contributors, see [CONTRIBUTING.md](CONTRIBUTING.md). To report a security issue, see [SECURITY.md](SECURITY.md). GeCo Desktop is released under the [MIT License](LICENSE).
