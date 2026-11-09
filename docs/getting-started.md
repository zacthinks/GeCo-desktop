# Create your first GeCo Desktop project

GeCo Desktop guides you from a collection of texts into [GeCo's geometric coding workspace](https://github.com/zacthinks/GeCo). You can start without Python or command-line tools.

For the larger research ideas, see the [GeCo Desktop introduction](../README.md) and the [GeCo workflow](https://github.com/zacthinks/GeCo).

## 1. Install and open GeCo Desktop

Use the [Windows or macOS installation instructions](../README.md#download-and-install). During the development preview, installers are available as downloadable artifacts from successful native-build workflow runs, not as an official public release.

Open **GeCo Desktop**. On the **Home** tab, choose **New project…**.

## 2. Create a research project

Give the project a name and choose its parent folder. GeCo Desktop creates a folder ending in `.gecod`, which contains your saved research project.

Under **Additional processing features**, select any optional tools you expect to need, such as PDF text extraction, sentence-transformer embeddings, or spaCy pipelines. You can leave these unchecked for a simple text project.

Choose **Create research project**. For a new scientific environment, Desktop may request permission to download and install the software needed to process your corpus. This can take some time, especially with optional features. You do not need to install Python yourself.

**Tip:** For a first experiment, begin with a small CSV file containing an identifier, a text column, and perhaps some metadata such as the source, date, or group.

## 3. Import your documents

Go to **2 · Import**. Choose a source type and select a file or folder. Depending on the format, Desktop can import CSV, Excel, JSONL, Parquet, TXT, or PDF sources.

Inspect the detected source information. For tabular files, select which columns contain your text and which are metadata. Metadata describes observations—such as a document's category or date—and can be useful for filtering and interpretation later.

Choose **Import documents**. Your imported data becomes part of the underlying [TeAL](https://github.com/zacthinks/text-analysis-lab) research project.

## 4. Preview and prepare your texts

Go to **3 · Prepare**. Select the imported artifact, an operation, and the appropriate source text field.

You can choose a bounded preview of **First rows** or a **Random sample**, or use **Try operation** to compare the result before applying it. The **Before** and **After** tabs show the sample. These previews do not create saved artifacts or represent full-corpus statistics.

Depending on your corpus and available features, you can:

- Clean text with regular-expression substitutions.
- Extract text and metadata using named patterns.
- Split text into smaller observations using delimiters or supported language tools.
- Create word-count and TF-IDF representations, or prepare numerical representations and reduced views for exploration.
- Use sentence embeddings when their required models have been installed.

When the preview looks right, give the result a name under **Save step as** and select **Apply to all rows**. Each accepted step creates a saved TeAL artifact with its own analytical history. You can use a previously saved artifact as the source for another operation.

For a quick first run, create a word-count representation, transform it to TF-IDF if appropriate, and prepare a suitable geometry and view. The important choice is not a particular algorithm but **which relationships among texts you want to investigate**.

## 5. Review and open your GeCo workspace

Go to **4 · Finalize**. Select the documents and prepared text you want to code, the text field to read, a geometry, and—if available—a lower-dimensional projection for visualization.

Review the selections, then choose **Create coding workspace**. When that succeeds, choose **Open coding workspace**. GeCo opens in your ordinary web browser, served locally from your own computer.

GeCo's core research workflow includes:

**Explore:** Navigate geometries and views, read observations in context, find patterns and exceptions, and begin coding.

**Develop:** Make and revise coding judgments, train code-specific classifiers, and review informative examples suggested by active learning.

**Apply & Review:** Generate coding proposals for more of the corpus and decide which to accept, revise, or leave unreviewed.

You can move among these workspaces as your understanding develops. For more detail, see the [GeCo README](https://github.com/zacthinks/GeCo).

## 6. Reopen your work

Your project remains in its `.gecod` folder.

To come back later, use **Open project…** on the Home tab, or choose a project from **Recent projects**. Desktop also provides an **Active Sessions** tab where you can reopen a running GeCo session in the browser or stop it. Stopping a session does not erase saved research data.

If you close Desktop while the managed GeCo browser session is still running, you can generally reconnect from Desktop when you return.

**Moving a project:** Close the active GeCo session before copying or moving your project folder. Its stored data and completed representations travel with it, though original source files may still be needed if you decide to rerun file-based imports. A different computer may require you to approve installation of a compatible scientific environment.

## Common questions

**Do I need to know Python?** No. You can install the application, prepare data, and use the full GeCo browser workspace through graphical interfaces.

**Why is the application downloading software?** GeCo Desktop manages a separate scientific environment for TeAL and GeCo. It may need to download that environment on first use. Some text-processing and embedding tools require additional models, which you can manage explicitly.

**Can I change the text preparation after creating the coding workspace?** Initial preparation is finalized when the linked GeCo workspace is created. To fundamentally change that setup through Desktop, create another project. Researchers using TeAL's Python API can work with the underlying TeAL project more flexibly.

**Where is my data?** In the `.gecod` project folder you chose. TeAL stores the scientific artifacts, representations, and history; GeCo stores the related coding workspace. Desktop's shared software environments and model caches live outside the project.

**Can I continue the project using Python?** Yes. Every Desktop project is also a [Text Analysis Lab project](https://github.com/zacthinks/text-analysis-lab). You or a collaborator can open the underlying project programmatically for more extensive analytical workflows.

**Is GeCo a statistical inference system?** Not by itself. Geometric coding supports exploration, interpretation, and the development and application of coding models. Population inference requires an appropriate separate inferential design.

---

**Next:** [Learn about geometric coding](../README.md#what-is-geometric-coding) · [Explore GeCo](https://github.com/zacthinks/GeCo) · [Extend your analysis with TeAL](https://github.com/zacthinks/text-analysis-lab)
