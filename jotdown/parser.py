# -*- coding: utf-8 -*-

from jotdown.lexer import *
from jotdown.classes import *
import jotdown.globalv as globalv

import sys


def parse(file):
	# Block-level "parser"
	blocks = get_blocks(file)
	nodes = []
	for block in blocks:
		if block_is_horizontal_rule(block):
			nodes.append(HorizontalRule())

		elif block_is_heading(block):
			level, text = lex_heading(block)
			subnodes = []
			for line in text:
				subnodes.append(Node(parse_text(line)))
			nodes.append(Heading(level, subnodes))

		elif block_is_list(block):
			list_stack = []
			indent_stack = [-1]

			for line in block:
				# TODO: This is really ugly
				list_type = 'checklist'  # by default
				m = re_checklistitem.match(line)
				if not m:
					list_type = 'unordered'
					m = re_ulistitem.match(line)
					if not m:
						list_type = 'ordered'
						m = re_olistitem.match(line)
						if not m:
							raise Exception('Malformed list item: ' + line)

				new_indent = len(m.group(1))

				if new_indent > indent_stack[-1]:
					# Need to create new nested lists
					while new_indent > indent_stack[-1]:
						indent_stack.append(indent_stack[-1] + 1)

						if list_type == 'ordered':
							olist_type, start = lex_olist(m)
							list_stack.append(OList(list_type=olist_type, start=start))
						elif list_type == 'unordered':
							list_stack.append(UList())
						elif list_type == 'checklist':
							list_stack.append(CheckList())
				elif new_indent < indent_stack[-1]:
					# Need to close nested lists
					while new_indent < indent_stack[-1]:
						indent_stack.pop()
						closed_list = list_stack.pop()
						list_stack[-1].children[-1].children.append(closed_list)
				if isinstance(list_stack[-1], CheckList):
					m = re_checklistitem.match(line)
					checked = bool(m.group(2))
					list_stack[-1].children.append(ChecklistItem(checked, parse_text(list_item_text(line))))
				else:
					list_stack[-1].children.append(ListItem(parse_text(list_item_text(line))))

			# Finih closing remaining nested lists
			while len(list_stack) > 1:
				closed_list = list_stack.pop()
				list_stack[-1].children.append(closed_list)

			nodes.append(list_stack[0])

		elif block_is_code(block):
			nodes.append(CodeBlock(map(Plaintext, block[1:-1])))

		elif block_is_math(block):
			nodes.append(MathBlock([parse_math(replace_math('\n'.join(block[1:-1])))]))

		elif block_is_md_table(block):
			header_content = block[0].split('|')
			header = [TableHeader(parse_text(i)) for i in header_content]

			alignment = list(map(cell_align, block[1].split('|')))

			# Check if there is a caption
			md_table = block[2:]
			caption = None
			if len(block) > 5:
				for char in block[-2]:
					if char not in '\t\n -':
						break
				else:
					caption = parse_text(block[-1])
					md_table = block[2:-2]

			table = Table(caption, alignment, [TableRow(header)])

			for line in md_table:
				cells = []
				for content, align in zip(line.split('|'), alignment):
					cells.append(TableCell(align, parse_text(content)))
				table.children.append(TableRow(cells))

			nodes.append(table)

		elif block_is_blockquote(block):
			def remove_gt(line):
				if line[0] == '>':
					return parse_text(line[1:])
				else:
					return parse_text(line)
			subnodes = []
			for line in block:
				subnodes.append(Node(remove_gt(line)))
			nodes.append(Blockquote(subnodes))

		else:
			subnodes = []
			for line in block:
				text_nodes = parse_text(line)
				if text_nodes:
					subnodes.append(Node(text_nodes))
			if subnodes:
				nodes.append(Paragraph(subnodes))

	return Document(nodes)


def parse_text(text):
	# (Formattable text)-level parser

	# Start the parser up with a dummy top-level node
	stack = ['Dummy_OPEN']
	node_stack = [Node()]
	debug_text = text[:50]

	for token, groups in get_text_tokens(text):
		if '_OPEN' in token or '_CLOSE' in token:
			# General rule for NODE_OPEN or NODE_CLOSE tokens
			node, type = token.split('_')

			if type == 'OPEN':
				stack.append(token)
				node_class = globals()[node]
				node_stack.append(node_class())
			else:

				tos_token = stack[-1]
				if '_' in tos_token:
					tos_node, tos_type = tos_token.split('_')
					if tos_node == node and tos_type == 'OPEN':
						stack.pop()
						closed_node = node_stack.pop()
						node_stack[-1].children.append(closed_node)
					else:
						raise Exception("Expected closing tag for %s, found %s" % (tos_token, token))
				else:
					raise Exception("Malformed document at %s" % text)

		elif '_AMB' in token:
			# General rules for tags opened and closed by the same token
			if token == stack[-1]:
				# Close the node
				stack.pop()
				closed_node = node_stack.pop()
				node_stack[-1].children.append(closed_node)
			else:
				# Open a node
				node, _ = token.split('_')
				stack.append(token)
				node_class = globals()[node]
				node_stack.append(node_class())

		elif token == "Plaintext":
			node_stack[-1].children.append(Plaintext(groups[0]))

		elif token == "Math":
			node_stack[-1].children.append(parse_math(replace_math(groups[0])))

		elif token == "ImplicitLink":
			node_stack[-1].children.append(ImplicitLink(groups[0]))

		elif token == "ImplicitEmail":
			node_stack[-1].children.append(ImplicitEmail(groups[0]))

		elif token == "Link":
			text, href = groups
			node_stack[-1].children.append(Link(Node(parse_text(text)), href))

		elif token == "ReferenceLink":
			cited_text, ref_key = groups
			node_stack[-1].children.append(ReferenceLink(Node(parse_text(cited_text)), ref_key))
			globalv.references[ref_key] = None  # Save its place in the OrderedDict

		elif token == "ReferenceDef":
			ref_key, reference_text = groups

			# TODO: Should parse on emit, or only when reference mode is enabled
			globalv.references[ref_key] = Node(parse_text(reference_text)), reference_text

		elif token == "Image":
			alt, src, title = groups
			#alt = Node(parse_text(alt))
			#title = Node(parse_text(title))
			node_stack[-1].children.append(Content(alt, src, title))

	if len(stack) > 1:
		raise Exception("Missing closing tag for %s at %s" % (stack[-1], repr(debug_text)))
	return node_stack[0].children


def parse_math(text):
	stack = ['Math_OPEN']
	node_stack = [Math()]
	debug_text = text[:50]

	for token, text in get_math_tokens(text):
		if '_OPEN' in token:
			node_class = globals()[token.split('_')[0]]
			stack.append(token)
			node_stack.append(node_class())
		elif '_CLOSE' in token:
			node, _ = token.split('_')
			tos_token = stack[-1]
			if '_' in tos_token:
				tos_node, tos_type = tos_token.split('_')
				if tos_node == node and tos_type == 'OPEN' \
					or tos_node in bracket_closable and tos_type == 'OPEN' and node == 'Brackets':
					stack.pop()
					closed_node = node_stack.pop()
					node_stack[-1].children.append(closed_node)
				else:
					raise Exception("Expected closing math tag for %s, found %s" % (tos_token, token))
			else:
				raise Exception("Malformed document at %s" % text)
		else:  # text tokens
			node_class = globals()[token]
			node_stack[-1].children.append(node_class(text))

	if len(stack) > 1:
		raise Exception("Missing closing math tag for %s at: %s" % (stack[-1], repr(debug_text)))
	return node_stack[0]


if __name__ == "__main__":

	if len(sys.argv) > 1:
		fname = sys.argv[1]
	else:
		fname = "text.jd"

	if len(sys.argv) > 2:
		out = sys.argv[2]
	else:
		out = "out.html"

	with open(fname, 'r') as f, open(out, 'wb') as fout:
		doc = parse(f)
		doc.name = fname
		fout.write(doc.emit_html())