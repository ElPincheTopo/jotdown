# -*- coding: utf-8 -*-
import html
import os
import re

import jotdown.globalv as globalv


# Abstract ---------------------------------
class Node:
	def __init__(self, children=None):
		self.children = children if children else []

	def emit_html(self, **kwargs):
		return ''.join(i.emit_html(**kwargs) for i in self.children)

	def emit_debug(self, indent=0, **kwargs):
		return ('\t' * indent) + type(self).__name__ + '\n' + ''.join(i.emit_debug(indent + 1, **kwargs) for i in self.children)


class TextNode(Node):
	def __init__(self, text):
		super().__init__()
		self.text = text

	def emit_html(self, **kwargs):
		return html.escape(self.text, quote=True)

	def emit_debug(self, level, **kwargs):
		summary = repr(self.text[:50])
		if len(self.text) > len(summary):
			summary += '...'
		res = ('\t' * level) + type(self).__name__ + ' ' + summary  + '\n'
		res += ''.join(i.emit_debug(level + 1, **kwargs) for i in self.children)
		return res

# For blocks -------------------------------------------------------------------------


class Document(Node):
	def __init__(self, children=None, name="Jotdown Document"):
		super().__init__(children)
		self.name = name

	def emit_html(self, css, ref_style=False, embed_css=True, **kwargs):
		if embed_css:
			with open(css) as style:
				css_string = '<style>%s</style>' % style.read()
		else:
			css_string = '<link rel="stylesheet" href="%s"/>' % css

		res = '<!DOCTYPE html><html><head><title>%s</title><meta charset="UTF-8">%s</head><body>'\
		      % (self.name, css_string)
		res += '\n'.join(block.emit_html(ref_style=ref_style, **kwargs) for block in self.children)
		if ref_style:
			res += '<footer>' + ReferenceList().emit_html(ref_style=ref_style, **kwargs) + '</footer>'
		res += '</body></html>'
		return res


class Heading(Node):
	def __init__(self, level, children=None):
		super().__init__(children)
		self.level = level

	def emit_html(self, **kwargs):
		# Sanitize the text for the id
		ident = ''.join(i.emit_html(**kwargs) for i in self.children).strip()
		ident = re.sub(r'<[^>]*>', '', ident, flags=globalv.re_flags)
		ident = re.sub(r'\s', '-', ident, flags=globalv.re_flags)
		ident = html.escape(ident)

		# Make sure it's unique on the whole document
		while ident in globalv.html_document_ids:
			ident += '_'
		globalv.html_document_ids.add(ident)

		return '<h%d id="%s">' % (self.level, ident)\
		       + '<br>'.join(i.emit_html(**kwargs) for i in self.children) + "</h%d>" % self.level


class HorizontalRule(Node):
	def emit_html(self, **kwargs):
		return "<hr/>"


class List(Node):
	pass


class UList(List):
	def emit_html(self, **kwargs):
		res = "<ul>"
		for item in self.children:
			res += item.emit_html(**kwargs)
		res += "</ul>"
		return res


class OList(List):
	def __init__(self, children=None, list_type='1', start=1):
		super().__init__(children)
		self.start = start
		self.list_type = list_type

	def emit_html(self, **kwargs):
		res = '<ol start="%s" type="%s">' % (self.start, self.list_type)
		for item in self.children:
			res += item.emit_html(**kwargs)
		res += "</ol>"
		return res


class ReferenceList(OList):
	def __init__(self):
		items = [ReferenceItem(ref_key, content[0]) for ref_key, content in globalv.references.items()]
		super().__init__(items, 1)

	def emit_html(self, **kwargs):
		res = '<ol class="references" start="%s">' % self.start
		for item in self.children:
			res += item.emit_html(**kwargs)
		res += '</ol>'
		return res


class ListItem(Node):
	def emit_html(self, **kwargs):
		res = ["<li><span>", ''.join(i.emit_html(**kwargs) for i in self.children[:-1])]

		if len(self.children) > 0 and isinstance(self.children[-1], List):
			res.append("</span>" + self.children[-1].emit_html(**kwargs))
		elif len(self.children) > 0:
			res.append(self.children[-1].emit_html(**kwargs) + "</span>")

		return ''.join(res)


class ReferenceItem(Node):
	def __init__(self, ref_key, content):
		self.ref_key = ref_key
		self.content = content
		super().__init__()

	def emit_html(self, **kwargs):
		return '<li><a id="%s"><span>%s</span></a></li>' % (self.ref_key, self.content.emit_html(**kwargs))


class Paragraph(Node):
	def emit_html(self, **kwargs):
		return "<p>" + "<br>".join(i.emit_html(**kwargs) for i in self.children) + "</p>"


class CodeBlock(Node):
	def emit_html(self, **kwargs):
		return "<code class=\"console\">" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</code>"


class MathBlock(Node):
	def emit_html(self, **kwargs):
		return "<div class='math'>" + "<br>".join(i.emit_html(**kwargs) for i in self.children) + "</div>"


class Blockquote(Node):
	def emit_html(self, **kwargs):
		return "<blockquote>" + "<br>".join(i.emit_html(**kwargs) for i in self.children) + "</blockquote>"


class Math(Node):
	def emit_html(self, **kwargs):
		return ''.join(i.emit_html(**kwargs) for i in self.children)


class Table(Node):
	def __init__(self, caption, children=None):
		super().__init__(children)
		self.caption = caption

	def emit_html(self, **kwargs):
		caption_html = ''
		if self.caption:
			caption_html = '<caption>' + ''.join(i.emit_html(**kwargs) for i in self.caption) + '</caption>'
		return '<table>' + caption_html + ''.join(i.emit_html(**kwargs) for i in self.children) + '</table>'


class TableRow(Node):
	def emit_html(self, **kwargs):
		return "<tr>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</tr>"


class TableHeader(Node):
	def emit_html(self, **kwargs):
		return "<th>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</th>"


class TableCell(Node):
	align_map = {
		0: 'left',
		1: 'center',
		2: 'right'
	}

	def __init__(self, align, children=None):
		super().__init__(children=children)
		self.align = align

	def emit_html(self, **kwargs):
		return "<td style=\"text-align: %s;\">" % self.align_map[self.align] +\
		       ''.join(i.emit_html(**kwargs) for i in self.children) + "</td>"


class Link(Node):
	def __init__(self, linked_text, url):
		# TODO: make this take a generic list of children instead of linked_text node
		super().__init__([linked_text])
		self.url = html.escape(url)
		self.linked_text = linked_text

	def emit_html(self, link_translation=None, **kwargs):
		url = self.url
		if link_translation:
			url = globalv.ext_translation(url, link_translation)

		return '<a href="' + url + '">' + self.linked_text.emit_html(link_translation=link_translation, **kwargs) + '</a>'


class ReferenceLink(Node):
	def __init__(self, cited_node, ref_key):
		# TODO:  make this take a generic list of children instead of a singleton cited_node
		super().__init__([cited_node])
		self.cited_node = cited_node
		self.ref_key = ref_key

	def emit_html(self, link_translation=None, ref_style=False, **kwargs):
		if not globalv.references[self.ref_key]:
			raise Exception("Missing definition for reference '%s'" % self.ref_key)
		if ref_style:
			place = list(globalv.references.keys()).index(self.ref_key) + 1
			emitted_html = self.cited_node.emit_html(link_translation=link_translation, ref_style=True)
			return '%s<cite>[<a href="#%s">%d</a>]</cite>' % (emitted_html, self.ref_key, place)
		else:
			_, href = globalv.references[self.ref_key]
			href = html.escape(href)
			if link_translation:
				href = link_translation(href, link_translation)
			return '<a href="%s">%s</a>' % (href, self.cited_node)


class Content(Node):
	def __init__(self, alt, src, title, children=None):
		super().__init__(children)
		self.alt = alt
		self.src = src
		self.title = title

	def emit_html(self, **kwargs):
		dtype = globalv.content_filetypes(self.src)
		if dtype == 'image':
			elem = '<img src="%s" title="%s" alt="%s">' % (self.src, self.title, self.alt)
		elif dtype == 'audio':
			elem = '<audio src="%s" controls>%s</audio>' % (self.src, self.alt)
		elif dtype == 'video':
			elem = '<video src="%s" controls>%s</video>' % (self.src, self.alt)
		elif dtype == 'flash':
			elem = '<object data="%s" type="application/x-shockwave-flash"></object>' % self.src
		else:
			elem = '<object data="%s"></object>' % self.src

		# TODO: make figures a command line option
		return '<figure>%s<figcaption>%s</figcaption></figure>' % (elem, self.title)


class ImplicitLink(TextNode):
	def emit_html(self, **kwargs):
		return "<a href=\"" + self.text + "\">" + self.text + "</a>"


class ImplicitEmail(TextNode):
	def emit_html(self, **kwargs):
		return "<a href=\"mailto:" + self.text + "\">" + self.text + "</a>"


# For text ----------------------------------------------------------------------

class Plaintext(TextNode):
	pass


class CodeInline(Node):
	def emit_html(self, **kwargs):
		return "<code>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</code>"


class Emph(Node):
	def emit_html(self, **kwargs):
		return "<em>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</em>"


class Strong(Node):
	def emit_html(self, **kwargs):
		return "<strong>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</strong>"


class StrongEmph(Node):
	def emit_html(self, **kwargs):
		return "<strong><em>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</em></strong>"


class Strikethrough(Node):
	def emit_html(self, **kwargs):
		return "<del>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</del>"


# MATH -------------------

class MathInline(Node):
	def emit_html(self, **kwargs):
		return '<span class="math">' + ''.join(i.emit_html(**kwargs) for i in self.children) + '</span>'


class Parenthesis(Node):
	def emit_html(self, **kwargs):
		return "(" + ''.join(i.emit_html(**kwargs) for i in self.children) + ")"

	def emit_mathml(self, **kwargs):
		return "<mfenced open=\"(\" close=\")\"><mrow>" + ''.join(i.emit_mathml(**kwargs) for i in self.children)\
		       +"</mrow></mfenced>"


class Braces(Node):
	def emit_html(self, **kwargs):
		return "{ " + ''.join(i.emit_html(**kwargs) for i in self.children) + " }"


class Brackets(Node):
	def emit_html(self, **kwargs):
		return ''.join(i.emit_html(**kwargs) for i in self.children)

	def emit_mathml(self, **kwargs):
		return ''.join(i.emit_mathml(**kwargs) for i in self.children)


class Sum(Node):
	def emit_html(self, **kwargs):
		# return "∑"
		return """
	<math><mstyle displaystyle="true"><mrow>
	<munderover>
		<mo>&sum;</mo>
		<mrow>%s</mrow><mrow>%s</mrow>
	</munderover>
	<mrow></mrow>
	</mrow></mstyle></math>
	""" % (self.children[0].emit_mathml(**kwargs),
		   self.children[1].emit_mathml(**kwargs)) + ''.join(i.emit_html(**kwargs) for i in self.children[2:])


class Prod(Node):
	def emit_html(self, **kwargs):
		# return "∏"
		return """
	<math><mstyle displaystyle="true"><mrow>
	<munderover>
		<mo>&prod;</mo>
		<mrow>%s</mrow><mrow>%s</mrow>
	</munderover>
	<mrow></mrow>
	</mrow></mstyle></math>
	""" % (self.children[0].emit_mathml(**kwargs),
		   self.children[1].emit_mathml(**kwargs)) + ''.join(i.emit_html(**kwargs) for i in self.children[2:])


class Int(Node):
	def emit_html(self, **kwargs):
		# return "∏"
		return """
	<math><mstyle displaystyle="true"><mrow>
	<munderover>
		<mo>&int;</mo>
		<mrow>%s</mrow><mrow>%s</mrow>
	</munderover>
	<mrow></mrow>
	</mrow></mstyle></math>
	""" % (self.children[0].emit_mathml(**kwargs),
		   self.children[1].emit_mathml(**kwargs)) + ''.join(i.emit_html(**kwargs) for i in self.children[2:])


class SuperscriptBrackets(Node):
	def emit_html(self, **kwargs):
		return "<sup>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</sup>"

	def emit_mathml(self, **kwargs):
		return "<msup><msrow></msrow><msrow>" + ''.join(i.emit_mathml(**kwargs) for i in self.children) + "</msrow></mssup>"


class SubscriptBrackets(Node):
	def emit_html(self, **kwargs):
		return "<sub>" + ''.join(i.emit_html(**kwargs) for i in self.children) + "</sub>"

	def emit_mathml(self, **kwargs):
		return "<msub><msrow></msrow><msrow>" + ''.join(i.emit_mathml(**kwargs) for i in self.children) + "</msrow></mssub>"


class Subscript(TextNode):
	def emit_html(self, **kwargs):
		return "<sub>" + html.escape(self.text, quote=True) + "</sub>"

	def emit_mathml(self, **kwargs):
		return "<msub><mrow></mrow><mrow>" + html.escape(self.text, quote=True) + "</mrow></mssub>"


class Superscript(TextNode):
	def emit_html(self, **kwargs):
		return "<sup>" + html.escape(self.text, quote=True) + "</sup>"

	def emit_mathml(self, **kwargs):
		return "<msup><mrow></mrow><mrow>" + html.escape(self.text, quote=True) + "</mrow></mssup>"


class Identifier(TextNode):
	def emit_html(self, **kwargs):
		return "<em>" + html.escape(self.text, quote=True) + "</em>"

	def emit_mathml(self, **kwargs):
		return "<mi>" + self.text + "</mi>"


class Operator(TextNode):
	def emit_html(self, **kwargs):
		return " %s " % html.escape(self.text, quote=True)

	def emit_mathml(self, **kwargs):
		return "<mo>" + self.text + "</mo>"


class Comment(TextNode):
	def emit_html(self, **kwargs):
		return ' %s ' % html.escape(self.text, quote=True)


class Number(TextNode):
	def emit_mathml(self, **kwargs):
		return "<mn>" + self.text + "</mn>"


class Newline(TextNode):
	def emit_html(self, **kwargs):
		return "<br>"
