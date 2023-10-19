import re
import sys
import json
from collections import defaultdict


def main(fn):
    js_chunks = {}
    with open(fn) as f:
        j = json.load(f)
        for entry in j["log"]["entries"]:
            fname = entry["request"]["url"].split("/")[-1]
            fname = fname.split("?")[0]
            content = entry["response"]["content"]["text"]
            mime = [
                x["value"]
                for x in entry["response"]["headers"]
                if x["name"] == "content-type"
            ]
            if mime != ["application/javascript"]:
                continue
            js_chunks[fname] = content
    chunk_dependencies = defaultdict(list)
    for chunk, content in js_chunks.items():
        for dep in js_chunks:
            if dep in content:
                chunk_dependencies[dep].append(chunk)

    if len(sys.argv) <= 2:
        search_string = input("Search for: ")
    else:
        search_string = sys.argv[2]

    shown_nodes = set()
    nodes = find_string(js_chunks, search_string, shown_nodes)
    while nodes:
        new_nodes = {}
        print("===============")
        for node_id, node_match in nodes.items():
            print(node_id)
            print(node_match)
            print()
            new_nodes.update(find_string(js_chunks, node_id, shown_nodes))
        nodes = new_nodes


def find_string(js_chunks, search_string, processed_nodes):
    ret = {}
    search_string = search_string.strip()
    for chunk_id, chunk_content in js_chunks.items():
        if chunk_id in processed_nodes:
            continue
        if search_string in chunk_content:
            pos = chunk_content.index(search_string)
            ret[chunk_id] = chunk_content[
                max(0, pos - 40) : min(pos + 40, len(chunk_content))
            ]
            processed_nodes.add(chunk_id)
    return ret


if __name__ == "__main__":
    main(sys.argv[1])
