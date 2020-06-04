# Copyright 2020 Katteli Inc.
# TestFlows Test Framework (http://testflows.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys
import json
import time
import base64

from datetime import datetime

import testflows._core.cli.arg.type as argtype

from testflows._core import __version__
from testflows._core.cli.arg.common import epilog
from testflows._core.cli.arg.common import HelpFormatter
from testflows._core.flags import Flags, SKIP
from testflows._core.testtype import TestType
from testflows._core.cli.arg.handlers.handler import Handler as HandlerBase
from testflows._core.cli.arg.handlers.report.copyright import copyright
from testflows._core.transform.log.pipeline import ResultsLogPipeline
from testflows._core.utils.timefuncs import localfromtimestamp, strftimedelta

logo = '<img class="logo" src="data:image/png;base64,%(data)s" alt="logo"/>'
testflows = '<span class="testflows-logo"></span> [<span class="logo-test">Test</span><span class="logo-flows">Flows</span>]'
testflows_em = testflows.replace("[", "").replace("]", "")

template = """
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/5.15.0/d3.js">
</script>
<section class="clearfix">%(logo)s%(confidential)s%(copyright)s</section>

---
# Test Map Report
%(body)s
  
---
Generated by %(testflows)s Open-Source Test Framework

[<span class="logo-test">Test</span><span class="logo-flows">Flows</span>]: https://testflows.com
[ClickHouse]: https://clickhouse.yandex

<script>
window.onload = function() {
  window.chart = chart();
  window.tests = tests();
};
</script>
"""

cdir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(cdir, "chart.css"), encoding="utf-8") as fd:
    chart_style = fd.read()

with open(os.path.join(cdir, "chart.js"), encoding="utf-8") as fd:
    chart_script = fd.read()

with open(os.path.join(cdir, "tests.js"), encoding="utf-8") as fd:
    tests_script = fd.read()

class Formatter:
    def format_logo(self, data):
        if not data["company"].get("logo"):
            return ""
        data = base64.b64encode(data["company"]["logo"]).decode("utf-8")
        return '\n<p>' + logo % {"data": data} + "</p>\n"

    def format_confidential(self, data):
        if not data["company"].get("confidential"):
            return ""
        return f'\n<p class="confidential">Document status - Confidential</p>\n'

    def format_copyright(self, data):
        if not data["company"].get("name"):
            return ""
        return (f'\n<p class="copyright">\n'
            f'{copyright(data["company"]["name"])}\n'
            "</p>\n")

    def format_metadata(self, data):
        metadata = data["metadata"]
        s = (
            "\n\n"
            f"||**Date**||{localfromtimestamp(metadata['date']):%b %d, %Y %-H:%M}||\n"
            f'||**Framework**||'
            f'{testflows} {metadata["version"]}||\n'
        )
        return s + "\n"

    def format_paths(self, data):
        s = '\n##Tests\n\n'

        def get_paths(paths):
            graph_paths = []

            def get_path(path):
                nodes = []
                links = []
                l = len(path)
                for i, step in enumerate(path):
                    nodes.append(step["node_uid"])
                    if i + 1 < l:
                        links.append({"source": step["node_uid"], "target": path[i + 1]["node_uid"]})
                return {"nodes": nodes, "links": links}

            for test, path in paths.items():
                graph_paths.append({"test": test, "path": get_path(path)})

            return graph_paths

        s += '<div id="tests-list" class="with-border" style="padding: 15px; max-height: 30vh; overflow: auto;"></div>\n'
        s += '<script>\n'
        s += f'{tests_script % {"paths": json.dumps(get_paths(data["paths"]), indent=2)}}\n'
        s += '</script>\n'
        return s + "\n"

    def format_map(self, data):
        def gather_links(map_nodes, gnodes):
            links = []
            for map_node in map_nodes:
                for n in map_node["node_nexts"]:
                    links.append({"source": map_node["node_uid"], "target": n, "type": "link"})
                for n in map_node["node_ins"]:
                    links.append({"source": map_node["node_uid"], "target": n, "type": "inner link"})
                for n in map_node["node_outs"]:
                    links.append({"source": n, "target": map_node["node_uid"], "type": "inner link"})

            for link in links:
                for node in gnodes:
                    children_links = node["children"]["links"]
                    children_nodes = set(node["children"]["nodes"])
                    for child in children_nodes:
                        if child == link["source"] or child == link["target"]:
                            if ((link["source"] in children_nodes or link["source"] == node["id"])
                                    and (link["target"] in children_nodes or link["target"] == node["id"])):
                                children_links.append(link)

            return links

        def gather_nodes(map_nodes):
            gnodes = []
            for map_node in map_nodes:
                gnodes.append({
                    "id": map_node["node_uid"],
                    "type": "unvisited",
                    "name": map_node["node_name"],
                    "module": map_node["node_module"],
                    "next": [n for n in map_node["node_nexts"]],
                    "children": {
                        "nodes": set(),
                        "links": []
                    }
                })

                def find_map_node(node):
                    for map_node in map_nodes:
                        if map_node["node_uid"] == node:
                            return map_node
                    return None

                def find_all_children(node, start, children):
                    if node in children:
                        return
                    if node == start["node_uid"]:
                        return
                    children.add(node)

                    map_node = find_map_node(node)
                    if not map_node or map_node["node_ins"] or map_node["node_outs"]:
                        return
                    for n in map_node["node_nexts"]:
                        find_all_children(n, start, children)

                for n in map_node["node_ins"] + map_node["node_outs"]:
                    find_all_children(n, map_node, gnodes[-1]["children"]["nodes"])
                gnodes[-1]["children"]["nodes"] = list(gnodes[-1]["children"]["nodes"])

            return gnodes

        map_nodes = data["map"]

        gnodes = gather_nodes(map_nodes)
        glinks = gather_links(map_nodes, gnodes)

        chart_nodes = json.dumps(gnodes, indent=2)
        chart_links = json.dumps(glinks, indent=2)

        s = (
            '\n##Map\n\n'
            '<style>\n'
            f'{chart_style}\n'
            '</style>\n'
            '<div><div id="map-chart"></div></div>\n'
            '<script>\n'
            f'{chart_script % {"nodes": chart_nodes, "links": chart_links}}\n'
            '</script>\n'
        )
        return s + "\n"

    def format(self, data):
        body = ""
        body += self.format_metadata(data)
        body += self.format_paths(data)
        body += self.format_map(data)
        return template.strip() % {
            "testflows": testflows,
            "logo": self.format_logo(data),
            "confidential": self.format_confidential(data),
            "copyright": self.format_copyright(data),
            "body": body}

class Handler(HandlerBase):
    @classmethod
    def add_command(cls, commands):
        parser = commands.add_parser("map", help="map report", epilog=epilog(),
            description="Generate map report.",
            formatter_class=HelpFormatter)

        parser.add_argument("input", metavar="input", type=argtype.file("r", bufsize=1, encoding="utf-8"),
                nargs="?", help="input log, default: stdin", default="-")
        parser.add_argument("output", metavar="output", type=argtype.file("w", bufsize=1, encoding="utf-8"),
                nargs="?", help='output file, default: stdout', default="-")
        parser.add_argument("--format", metavar="type", type=str,
            help="output format, default: md (Markdown)", choices=["md"], default="md")
        parser.add_argument("--copyright", metavar="name", help="add copyright notice", type=str)
        parser.add_argument("--confidential", help="mark as confidential", action="store_true")
        parser.add_argument("--logo", metavar="path", type=argtype.file("rb"),
                help='use logo image (.png)')

        parser.set_defaults(func=cls())

    def metadata(self):
        return {
            "date": time.time(),
            "version": __version__,
        }

    def company(self, args):
        d = {}
        if args.copyright:
            d["name"] = args.copyright
        if args.confidential:
            d["confidential"] = True
        if args.logo:
            d["logo"] = args.logo.read()
        return d

    def paths(self, results):
        d = {}
        tests = list(results["tests"].values())

        def get_path(test, idx):
            started = test["test"]["message_time"]
            ended = test["result"]["message_time"]
            path = []

            for t in tests[idx:]:
                flags = Flags(t["test"]["test_flags"])
                if flags & SKIP and settings.show_skipped is False:
                    continue
                if t["test"]["message_time"] > ended:
                    break
                if t["test"]["test_id"].startswith(test["test"]["test_id"]):
                    if t["test"]["node"]:
                        path.append(t["test"]["node"])

            return path

        for idx, name in enumerate(results["tests"]):
            test = results["tests"][name]
            flags = Flags(test["test"]["test_flags"])
            if flags & SKIP and settings.show_skipped is False:
                continue
            if getattr(TestType, test["test"]["test_type"]) < TestType.Test:
                continue
            d[name] = get_path(test, idx)

        return d

    def data(self, results, args):
        d = dict()
        d["metadata"] = self.metadata()
        d["company"] = self.company(args)
        d["map"] = list(results["tests"].values())[0]["test"]["map"]
        d["paths"] = self.paths(results)
        return d

    def generate(self, formatter, results, args):
        output = args.output
        output.write(
            formatter.format(self.data(results, args))
        )
        output.write("\n")

    def handle(self, args):
        results = {}
        formatter = Formatter()
        ResultsLogPipeline(args.input, results).run()
        self.generate(formatter, results, args)
