from __future__ import absolute_import, unicode_literals

import re
from builtins import str
from CommonMark.common import escape_xml


reHtmlTag = re.compile(r'\<[^>]*\>')
reUnsafeProtocol = re.compile(
    r'^javascript:|vbscript:|file:|data:', re.IGNORECASE)
reSafeDataProtocol = re.compile(
    r'^data:image\/(?:png|gif|jpeg|webp)', re.IGNORECASE)


def tag(name, attrs=[], selfclosing=False):
    """Helper function to produce an HTML tag."""
    result = '<' + name
    for attr in attrs:
        result += ' {0}="{1}"'.format(attr[0], attr[1])
    if selfclosing:
        result += ' /'

    result += '>'
    return result


def potentially_unsafe(url):
    return re.search(reUnsafeProtocol, url) and not \
        re.search(reSafeDataProtocol, url)


class HtmlRenderer(object):

    def __init__(self, options={}):
        # by default, soft breaks are rendered as newlines in HTML.
        # set to "<br />" to make them hard breaks
        # set to " " if you want to ignore line wrapping in source
        self.softbreak = '\n'
        self.options = options

    def out(self, s):
        if self.disable_tags > 0:
            self.buf += re.sub(reHtmlTag, '', s)
        else:
            self.buf += s
        self.last_out = s

    def cr(self):
        if self.last_out != '\n':
            self.buf += '\n'
            self.last_out = '\n'

    def renderNodes(self, block):
        walker = block.walker()
        self.buf = ''
        self.last_out = '\n'
        self.disable_tags = 0

        event = walker.nxt()
        while event is not None:
            entering = event['entering']
            node = event['node']

            attrs = []
            if self.options.get('sourcepos'):
                pos = node.sourcepos
                if pos:
                    attrs.push([
                        'data-sourcepos',
                        pos[0][0] + ':' + pos[0][1] + '-' +
                        pos[1][0] + ':' + pos[1][1]])

            try:
                render_fn = getattr(self, 'render' + node.t)
            except AttributeError:
                raise ValueError('Unknown node type {0}'.format(node.t))
            render_fn(event, node, attrs, entering)
            event = walker.nxt()
        return self.buf

    def renderText(self, event, node, attrs, entering):
        self.out(escape_xml(node.literal, False))

    def renderSoftbreak(self, event, node, attrs, entering):
        self.out(self.softbreak)

    def renderHardbreak(self, event, node, attrs, entering):
        self.out(tag('br', [], True))
        self.cr()

    def renderEmph(self, event, node, attrs, entering):
        self.out(tag('em' if entering else '/em'))

    def renderStrong(self, event, node, attrs, entering):
        self.out(tag('strong' if entering else '/strong'))

    def renderHtmlInline(self, event, node, attrs, entering):
        if self.options.get('safe'):
            self.out('<!-- raw HTML omitted -->')
        else:
            self.out(node.literal)

    def renderCustomInline(self, event, node, attrs, entering):
        if entering and node.on_enter:
            self.out(node.on_enter)
        elif not entering and node.on_exit:
            self.out(node.on_exit)

    def renderLink(self, event, node, attrs, entering):
        if entering:
            if not (self.options.get('safe') and
                    potentially_unsafe(node.destination)):
                attrs.append([
                    'href',
                    escape_xml(node.destination, True)
                ])
            if node.title:
                attrs.append(['title', escape_xml(node.title, True)])
            self.out(tag('a', attrs))
        else:
            self.out(tag('/a'))

    def renderImage(self, event, node, attrs, entering):
        if entering:
            if self.disable_tags == 0:
                if self.options.get('safe') and \
                   potentially_unsafe(node.destination):
                    self.out('<img src="" alt="')
                else:
                    self.out(
                        '<img src="{0}" alt="'.format(
                            escape_xml(node.destination, True)))
            self.disable_tags += 1
        else:
            self.disable_tags -= 1
            if self.disable_tags == 0:
                if node.title:
                    self.out('" title="' +
                             escape_xml(node.title, True))
                self.out('" />')

    def renderCode(self, event, node, attrs, entering):
        self.out(
            tag('code') +
            escape_xml(node.literal, False) +
            tag('/code'))

    def renderDocument(self, event, node, attrs, entering):
        pass

    def renderParagraph(self, event, node, attrs, entering):
        grandparent = node.parent.parent
        if grandparent is not None and \
           grandparent.t == 'List' and \
           grandparent.list_data.get('tight'):
            pass
        else:
            if entering:
                self.cr()
                self.out(tag('p', attrs))
            else:
                self.out(tag('/p'))
                self.cr()

    def renderBlockQuote(self, event, node, attrs, entering):
        if entering:
            self.cr()
            self.out(tag('blockquote', attrs))
            self.cr()
        else:
            self.cr()
            self.out(tag('/blockquote'))
            self.cr()

    def renderItem(self, event, node, attrs, entering):
        if entering:
            self.out(tag('li', attrs))
        else:
            self.out(tag('/li'))
            self.cr()

    def renderList(self, event, node, attrs, entering):
        tagname = 'ul' if node.list_data['type'] == 'Bullet' else 'ol'
        if entering:
            try:
                start = node.list_data['start']
            except KeyError:
                start = None
            if start is not None and start != 1:
                attrs.append(['start', str(start)])
            self.cr()
            self.out(tag(tagname, attrs))
            self.cr()
        else:
            self.cr()
            self.out(tag('/' + tagname))
            self.cr()

    def renderHeading(self, event, node, attrs, entering):
        tagname = 'h' + str(node.level)
        if entering:
            self.cr()
            self.out(tag(tagname, attrs))
        else:
            self.out(tag('/' + tagname))
            self.cr()

    def renderCodeBlock(self, event, node, attrs, entering):
        info_words = re.split(r'\s+', node.info) if node.info else []
        if len(info_words) > 0 and len(info_words[0]) > 0:
            attrs.append([
                'class',
                'language-' + escape_xml(info_words[0], True)
            ])
        self.cr()
        self.out(tag('pre') + tag('code', attrs))
        self.out(escape_xml(node.literal, False))
        self.out(tag('/code') + tag('/pre'))
        self.cr()

    def renderHtmlBlock(self, event, node, attrs, entering):
        if self.options.get('safe'):
            self.out('<!-- raw HTML omitted -->')
        else:
            self.out(str(node.literal))
        self.cr()

    def renderCustomBlock(self, event, node, attrs, entering):
        self.cr()
        if entering and node.on_enter:
            self.out(node.on_enter)
        elif not entering and node.on_exit:
            self.out(node.on_exit)
        self.cr()

    def renderThematicBreak(self, event, node, attrs, entering):
        self.cr()
        self.out(tag('hr', attrs, True))
        self.cr()

    render = renderNodes
