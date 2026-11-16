import asyncio
import json
from pathlib import Path
import socket
import sys
import unittest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client
    import uvicorn
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

from math_reader.document import parse_document
from test_math_reader import PAPER, annotations
from test_exposition import DRAFT, review


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(SDK_AVAILABLE, "Install optional MCP dependencies for protocol integration")
class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_streamable_http_handshake_and_real_measurement(self):
        from math_exposition.mcp import build_server
        app = build_server(ROOT).streamable_http_app()
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(100):
                if server.started or serving.done():
                    break
                await asyncio.sleep(0.02)
            self.assertTrue(server.started)
            async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("prepare_mathematical_rewrite", {"text": "若条件成立，则结论成立。"})
                    self.assertFalse(result.isError)
                    data = json.loads(next(c.text for c in result.content if c.type == "text"))
                    self.assertEqual(data["statistics"]["status"], "measured")
        finally:
            server.should_exit = True
            await serving
            listener.close()

    async def test_stdio_handshake_long_upload_graph_and_audit(self):
        params = StdioServerParameters(command=sys.executable,
                                      args=["-m", "math_exposition.mcp", "--resources", str(ROOT)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                self.assertEqual(len(listing.tools), 9)

                async def call(name, **kwargs):
                    result = await session.call_tool(name, kwargs)
                    self.assertFalse(result.isError, result.content)
                    return json.loads(next(c.text for c in result.content if c.type == "text"))

                text = PAPER + "\n" + "😀 full context " * 2500
                first = await call("upload_paper_chunk", text=text[:10000], index=0, total=3)
                upload_id = first["upload_id"]
                self.assertFalse(first["complete"])
                # Out-of-order transport is allowed; concatenation remains by declared index.
                await call("upload_paper_chunk", text=text[20000:], index=2, total=3, upload_id=upload_id)
                final = await call("upload_paper_chunk", text=text[10000:20000], index=1, total=3, upload_id=upload_id)
                self.assertTrue(final["complete"])
                self.assertEqual(final["characters"], len(text))
                identity = final["document_id"]
                part1 = await call("read_paper_source", document_id=identity, max_chars=20000)
                part2 = await call("read_paper_source", document_id=identity, start=part1["next_start"], max_chars=20000)
                self.assertEqual(part1["quote"] + part2["quote"], text)
                doc = parse_document(text)
                data = annotations(doc)
                graph = await call("query_proof_dependencies", document_id=identity, annotations=data)
                self.assertEqual(graph["prerequisite_order"], ["n1", "n2", "n4", "n6"])
                self.assertFalse(graph["findings"])
                task = await call("prepare_explanation_task", stage="motivation", document_id=identity, annotations=data)
                self.assertEqual(task["prompt_version"], "2.0.1")
                audited = await call("audit_mathematical_exposition", document_id=identity, annotations=data,
                                     baseline=DRAFT, candidate=DRAFT, review=review(doc))
                self.assertTrue(audited["editorial_revision_allowed"])
                editorial = await call("prepare_explanation_task", stage="editorial", document_id=identity,
                                       annotations=data, baseline=DRAFT, candidate=DRAFT, audit=audited)
                self.assertEqual(editorial["measured_feedback"]["text_sha256"], audited["candidate_sha256"])
                self.assertIn("writing_guide", editorial)
                bad = await session.call_tool("read_paper_source", {"document_id": identity, "start": -1})
                self.assertTrue(bad.isError)
                bad = await session.call_tool("get_reference", {"name": "../README.md"})
                self.assertTrue(bad.isError)
