# Real GeCo Desktop smoke example

84 synthetic DBpedia-14-style documents with original fictional descriptions; not copied from DBpedia.

Run `seed_workspace.py` with the separately provisioned scientific interpreter to create a real TeAL project, CountVectorizer, TF-IDF, SVD and linked GeCo. Run `smoke_test.py` with the app interpreter to test the current Desktop runner, a real Dash server, Desktop session reconnection, Stop and project relocation.

The source CSV lives outside the generated project. The project and scientific environment are never checked into the repository. A successful test prints `"result": "PASS"`. See `.github/workflows/real-integration.yml` for reproducible source pins and execution.

The wizard and OS installer are not yet implemented. The smoke test exercises the backend and portable project shape only.
