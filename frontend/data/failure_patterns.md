# MCP-Bench failure-mode analysis

_Generated from **374 failed runs** across **25 models**_ (every trace in `backend/traces/` where the programmatic check returned False). Embedded with `sentence-transformers/all-MiniLM-L6-v2`, clustered with HDBSCAN (min_cluster_size=4). 40 clusters surfaced; 306 runs clustered, 68 unclustered (noise).

Top 8 clusters by size are featured below. Cluster names are heuristic suggestions based on dominant signals — rename freely.

## Pattern 1 — Wrong final answer (tool calls succeeded, answer failed check)

**Size:** 15 runs &nbsp; &nbsp;**Mean tool calls:** 2.5 &nbsp; &nbsp;**Mean tool errors:** 0.7

**Status distribution:** {'answered': 9, 'model_error': 6}  
**Top models:** {'deepseek-v4-pro-together': 1, 'deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite': 1, 'gpt-oss-120b': 1, 'gpt-oss-120b__d-fetch-filesystem-github-memory-postgres-sqlite': 1}  
**Top task servers:** {'filesystem': 15}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>gpt-oss-20b</code> · <code>fs_014_delete_by_content</code> · status: <code>answered</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Three files are in your working directory. Exactly one of them contains the text 'DELETE ME'. Find that file and delete it. Leave the others untouched.

**Final agent text:** _(empty)_

**Check verdict:** file_not_exists=FAIL(path=C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\target.txt)

</details>

<details><summary><code>llama-4-scout-groq__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>fs_014_delete_by_content</code> · status: <code>model_error</code> · calls: 3 · errors: 0</summary>

**Task prompt:** Three files are in your working directory. Exactly one of them contains the text 'DELETE ME'. Find that file and delete it. Leave the others untouched.

**Final agent text:** _(empty)_

**Check verdict:** file_not_exists=FAIL(path=C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\target.txt)

</details>

<details><summary><code>gpt-oss-20b__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>fs_014_delete_by_content</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Three files are in your working directory. Exactly one of them contains the text 'DELETE ME'. Find that file and delete it. Leave the others untouched.

**Final agent text:** _(empty)_

**Check verdict:** file_not_exists=FAIL(path=C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\target.txt)

</details>

## Pattern 2 — Provider rate-limit wall (0 tokens, 0 calls)

**Size:** 13 runs &nbsp; &nbsp;**Mean tool calls:** 0.2 &nbsp; &nbsp;**Mean tool errors:** 0.2

**Status distribution:** {'model_error': 11, 'answered': 2}  
**Top models:** {'deepseek-v4-pro-together': 3, 'llama-3.3-70b-together': 3, 'llama-4-scout-groq': 3, 'qwen-2.5-7b': 3}  
**Top task servers:** {'github': 13}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>deepseek-v4-pro-together</code> · <code>gh_001_default_branch</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** What is the name of the default branch of the GitHub repository 'microsoft/vscode'?

**Final agent text:** _(empty)_

**Check verdict:** no final text (agent did not answer)

</details>

<details><summary><code>llama-3.3-70b-together</code> · <code>gh_001_default_branch</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** What is the name of the default branch of the GitHub repository 'microsoft/vscode'?

**Final agent text:** _(empty)_

**Check verdict:** no final text (agent did not answer)

</details>

<details><summary><code>qwen-2.5-7b</code> · <code>gh_001_default_branch</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** What is the name of the default branch of the GitHub repository 'microsoft/vscode'?

**Final agent text:** _(empty)_

**Check verdict:** no final text (agent did not answer)

</details>

## Pattern 3 — Wrong final answer (tool calls succeeded, answer failed check)

**Size:** 12 runs &nbsp; &nbsp;**Mean tool calls:** 2.2 &nbsp; &nbsp;**Mean tool errors:** 0.9

**Status distribution:** {'answered': 8, 'model_error': 4}  
**Top models:** {'deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite': 2, 'gpt-oss-20b': 1, 'gpt-oss-20b__d-fetch-filesystem-github-memory-postgres-sqlite': 1, 'llama-3.1-8b': 1}  
**Top task servers:** {'filesystem': 12}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>llama-3.1-8b__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>fs_010_count_lines</code> · status: <code>answered</code> · calls: 4 · errors: 0</summary>

**Task prompt:** There are several .log files in your working directory. Count the total number of lines across all of them and tell me the total. (A line is anything ending in a newline.)

**Final agent text:** The total number of lines across all the .log files is 9.

**Check verdict:** pattern='\\b10\\b'

</details>

<details><summary><code>llama-3.1-8b</code> · <code>fs_010_count_lines</code> · status: <code>answered</code> · calls: 5 · errors: 5</summary>

**Task prompt:** There are several .log files in your working directory. Count the total number of lines across all of them and tell me the total. (A line is anything ending in a newline.)

**Final agent text:** The total number of lines across all .log files in the working directory is not available because the path to the .log files is not provided. Please provide the correct path to the .log files.

**Check verdict:** pattern='\\b10\\b'

</details>

<details><summary><code>llama-4-scout-groq</code> · <code>fs_010_count_lines</code> · status: <code>answered</code> · calls: 4 · errors: 0</summary>

**Task prompt:** There are several .log files in your working directory. Count the total number of lines across all of them and tell me the total. (A line is anything ending in a newline.)

**Final agent text:** The total number of lines across all .log files is 9. 

Here is the calculation: 
- a.log has 3 lines 
- b.log has 2 lines 
- c.log has 5 lines 

3 + 2 + 5 = 9

**Check verdict:** pattern='\\b10\\b'

</details>

## Pattern 4 — Provider rate-limit wall (0 tokens, 0 calls)

**Size:** 11 runs &nbsp; &nbsp;**Mean tool calls:** 0.6 &nbsp; &nbsp;**Mean tool errors:** 0.1

**Status distribution:** {'model_error': 10, 'answered': 1}  
**Top models:** {'deepseek-v4-pro-together': 2, 'llama-3.1-8b': 2, 'llama-3.3-70b-together': 2, 'qwen-2.5-7b': 2}  
**Top task servers:** {'github': 11}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>gpt-oss-20b</code> · <code>gh_006_readme_keyword</code> · status: <code>model_error</code> · calls: 1 · errors: 0</summary>

**Task prompt:** Fetch the README of the 'modelcontextprotocol/python-sdk' repository on GitHub. Does it mention the Model Context Protocol? Answer yes or no.

**Final agent text:** _(empty)_

**Check verdict:** no final text (agent did not answer)

</details>

<details><summary><code>gpt-oss-120b</code> · <code>gh_006_readme_keyword</code> · status: <code>model_error</code> · calls: 1 · errors: 0</summary>

**Task prompt:** Fetch the README of the 'modelcontextprotocol/python-sdk' repository on GitHub. Does it mention the Model Context Protocol? Answer yes or no.

**Final agent text:** _(empty)_

**Check verdict:** no final text (agent did not answer)

</details>

<details><summary><code>llama-4-scout-groq</code> · <code>gh_006_readme_keyword</code> · status: <code>model_error</code> · calls: 1 · errors: 0</summary>

**Task prompt:** Fetch the README of the 'modelcontextprotocol/python-sdk' repository on GitHub. Does it mention the Model Context Protocol? Answer yes or no.

**Final agent text:** _(empty)_

**Check verdict:** no final text (agent did not answer)

</details>

## Pattern 5 — Heavy tool-call errors (bad arguments / wrong tool name)

**Size:** 11 runs &nbsp; &nbsp;**Mean tool calls:** 3.0 &nbsp; &nbsp;**Mean tool errors:** 2.9

**Status distribution:** {'model_error': 5, 'answered': 5, 'step_cap': 1}  
**Top models:** {'deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite': 3, 'llama-3.1-8b': 3, 'llama-3.1-8b__d-fetch-filesystem-github-memory-postgres-sqlite': 2, 'gpt-oss-20b': 1}  
**Top task servers:** {'fetch': 11}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>llama-3.1-8b__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>fetch_010_dual_source</code> · status: <code>model_error</code> · calls: 2 · errors: 2</summary>

**Task prompt:** Fetch both https://httpbin.org/uuid and https://httpbin.org/json. Tell me both: the uuid value, and the title of the slideshow.

**Final agent text:** _(empty)_

**Check verdict:** final_text_regex=FAIL(no final text)

</details>

<details><summary><code>deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>fetch_010_dual_source</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Fetch both https://httpbin.org/uuid and https://httpbin.org/json. Tell me both: the uuid value, and the title of the slideshow.

**Final agent text:** _(empty)_

**Check verdict:** final_text_regex=FAIL(no final text)

</details>

<details><summary><code>llama-3.3-70b-together</code> · <code>fetch_010_dual_source</code> · status: <code>step_cap</code> · calls: 20 · errors: 20</summary>

**Task prompt:** Fetch both https://httpbin.org/uuid and https://httpbin.org/json. Tell me both: the uuid value, and the title of the slideshow.

**Final agent text:** _(empty)_

**Check verdict:** final_text_regex=FAIL(no final text)

</details>

## Pattern 6 — Wrong final answer (tool calls succeeded, answer failed check)

**Size:** 11 runs &nbsp; &nbsp;**Mean tool calls:** 2.0 &nbsp; &nbsp;**Mean tool errors:** 1.9

**Status distribution:** {'answered': 6, 'model_error': 5}  
**Top models:** {'deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite': 1, 'llama-3.1-8b': 1, 'llama-3.1-8b__d-fetch-filesystem-github-memory-postgres-sqlite': 1, 'llama-3.3-70b-groq': 1}  
**Top task servers:** {'memory': 11}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>llama-3.1-8b</code> · <code>mem_002_entity_with_observation</code> · status: <code>model_error</code> · calls: 3 · errors: 3</summary>

**Task prompt:** Remember that 'Paris' is a city. Record an observation on it stating that it is the capital of France.

**Final agent text:** _(empty)_

**Check verdict:** no entity 'Paris'

</details>

<details><summary><code>deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>mem_002_entity_with_observation</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Remember that 'Paris' is a city. Record an observation on it stating that it is the capital of France.

**Final agent text:** _(empty)_

**Check verdict:** no entity 'Paris'

</details>

<details><summary><code>llama-3.3-70b-groq</code> · <code>mem_002_entity_with_observation</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Remember that 'Paris' is a city. Record an observation on it stating that it is the capital of France.

**Final agent text:** _(empty)_

**Check verdict:** no entity 'Paris'

</details>

## Pattern 7 — Provider rate-limit wall (0 tokens, 0 calls)

**Size:** 10 runs &nbsp; &nbsp;**Mean tool calls:** 0.0 &nbsp; &nbsp;**Mean tool errors:** 0.0

**Status distribution:** {'model_error': 9, 'answered': 1}  
**Top models:** {'deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite': 3, 'deepseek-v3': 1, 'deepseek-v4-flash': 1, 'deepseek-v4-pro': 1}  
**Top task servers:** {'filesystem': 10}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>deepseek-v3</code> · <code>fs_002_write_exact</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Create a file named 'greeting.txt' in your working directory containing exactly the text: Hello, MCP!

**Final agent text:** _(empty)_

**Check verdict:** missing file: C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\greeting.txt

</details>

<details><summary><code>deepseek-v4-flash</code> · <code>fs_002_write_exact</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Create a file named 'greeting.txt' in your working directory containing exactly the text: Hello, MCP!

**Final agent text:** _(empty)_

**Check verdict:** missing file: C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\greeting.txt

</details>

<details><summary><code>deepseek-v4-pro</code> · <code>fs_002_write_exact</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** Create a file named 'greeting.txt' in your working directory containing exactly the text: Hello, MCP!

**Final agent text:** _(empty)_

**Check verdict:** missing file: C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\greeting.txt

</details>

## Pattern 8 — Wrong final answer (tool calls succeeded, answer failed check)

**Size:** 10 runs &nbsp; &nbsp;**Mean tool calls:** 1.8 &nbsp; &nbsp;**Mean tool errors:** 0.7

**Status distribution:** {'answered': 6, 'model_error': 4}  
**Top models:** {'qwen-2.5-7b': 2, 'deepseek-v4-pro-together__d-fetch-filesystem-github-memory-postgres-sqlite': 1, 'gpt-oss-120b': 1, 'llama-3.1-8b': 1}  
**Top task servers:** {'filesystem': 10}

**Representative examples (nearest to cluster centroid):**

<details><summary><code>gpt-oss-120b</code> · <code>fs_013_increment_counter</code> · status: <code>answered</code> · calls: 1 · errors: 0</summary>

**Task prompt:** The file 'counter.txt' contains a single integer. Read it, add 1 to it, and write the new value back to 'counter.txt'.

**Final agent text:** _(empty)_

**Check verdict:** path=C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\counter.txt match=False

</details>

<details><summary><code>llama-3.3-70b-together__d-fetch-filesystem-github-memory-postgres-sqlite</code> · <code>fs_013_increment_counter</code> · status: <code>answered</code> · calls: 3 · errors: 2</summary>

**Task prompt:** The file 'counter.txt' contains a single integer. Read it, add 1 to it, and write the new value back to 'counter.txt'.

**Final agent text:** The value in 'counter.txt' is now 42.

**Check verdict:** path=C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\counter.txt match=False

</details>

<details><summary><code>llama-3.3-70b-groq</code> · <code>fs_013_increment_counter</code> · status: <code>model_error</code> · calls: 0 · errors: 0</summary>

**Task prompt:** The file 'counter.txt' contains a single integer. Read it, add 1 to it, and write the new value back to 'counter.txt'.

**Final agent text:** _(empty)_

**Check verdict:** path=C:\Users\KeerthanaS\projects\mcp-bench\backend\sandbox\counter.txt match=False

</details>

## Unclustered (noise): 68 runs

Failures too unique to cluster with the rest. Worth eyeballing for one-off bugs or task-specific weirdness.
