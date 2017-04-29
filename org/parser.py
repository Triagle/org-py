""" Module containing parser implementation and related functions. """
import re
import datetime
from enum import Enum


class Style(Enum):
    NONE = 1,
    UNDERLINE = 2,
    ITALICS = 3,
    BOLD = 4,
    STRIKE = 5,
    CODE = 6,
    VERBATIM = 7


class Node():
    """ Base node class. """
    def __init__(self, level, children):
        self.level = level
        self.children = children


class Drawer(Node):
    """ A node representing a drawer in an org mode document. """
    def __init__(self, name):
        self.name = name
        self.children = []

    def __repr__(self):
        return "{}: {}".format(self.name, self.children)


class Header(Node):
    """ A node representing a heading in an org mode document. """

    def __init__(self, level, text, tags):
        self.children = []
        self.level = level
        self.text = text
        self.tags = tags
        self.todo = None
        self.priority = None
        self.scheduled = None
        self.deadline = None

    def set_tags(self, tags):
        self.tags = tags

    def __repr__(self):
        return "{} {}".format(self.text, self.children)


class Directive(Node):
    """ A node containing directives describing the org mode document.
    Examples of a directive might include #+TITLE, which sets the title of the document. """
    def __init__(self, name, args):
        self.name = name
        self.args = args


def char_for_style(style):
    markup_dict = {
        Style.UNDERLINE: '_',
        Style.ITALICS: '/',
        Style.BOLD: '*',
        Style.STRIKE: '+',
        Style.CODE: '~',
        Style.VERBATIM: '=',
        Style.NONE: ''
    }
    return markup_dict[style]


class Element():
    """ A style element of representing a block of text. """
    def __init__(self, style, text):
        self.style = style
        self.text = text

    def __repr__(self):
        surround = char_for_style(self.style)
        return "{0}{1}{0}".format(surround, self.text)


class Link():
    """ Link element representing an org mode link, both it's url and
    displayed text. """
    def __init__(self, url, text):
        self.url = url
        self.text = text

    def __repr__(self):
        return '[[{}][{}]]'.format(self.url, self.text)


class Markup(Node):
    """ A node containing org mode markup (bold text, links, ...)"""
    def __init__(self, elements):
        self.elements = elements

    def __repr__(self):
        return ''.join([repr(el) for el in self.elements])


def markup_char(char):
    markup_dict = {
        '_': Style.UNDERLINE,
        '/': Style.ITALICS,
        '*': Style.BOLD,
        '+': Style.STRIKE,
        '~': Style.CODE,
        '=': Style.VERBATIM
    }
    if char in markup_dict:
        return markup_dict[char]
    else:
        return Style.NONE


def parse_date(date):
    """ Parse and org mode date stamp. """
    date_re = re.compile(r"<(\d{4})-(\d{2})-(\d{2}) .+?>")
    date = date.strip()
    date_match = re.match(date_re, date)
    if date_match:
        year = date_match.group(1)
        month = date_match.group(2)
        day = date_match.group(3)
        return datetime.date(int(year), int(month), int(day))
    else:
        return None


def parse_markup(string):
    """ Parse org mode markup into a Markup object containing multiple elements or links. """
    text_node = None
    markup = []
    index = 0
    link_re = re.compile(r"\[\s*?\[(.+)?\]\s*?\[(.+)?\]\s*?\]")
    while index < len(string):
        char = string[index]
        style = markup_char(char)
        found_matching = string.find(char, index + 1)
        link_match = None
        if char == '[':
            # Possibly a link
            link_match = re.match(link_re, string[index:])
        if link_match:
            link = Link(link_match.group(1), link_match.group(2))
            markup.append(link)
            (_, end_match) = link_match.span()
            index = end_match
        elif style != Style.NONE and found_matching != -1:
            # take until terminating character
            if text_node is not None:
                markup.append(Element(Style.NONE, text_node))
            text_node = None
            node_contents = string[index + 1:found_matching]
            markup.append(Element(style, node_contents))
            index = found_matching
        elif text_node is not None:
            text_node += char
        else:
            text_node = char
        index += 1
    if text_node is not None:
        markup.append(Element(Style.NONE, text_node))
    return Markup(markup)


def peek(stack):
    """ Take the top element of a list (stack). """
    if len(stack) == 0:
        return None
    else:
        return stack[-1]


def first_word(text):
    space = text.find(' ')
    if space == -1:
        return text
    else:
        return text[:space]


def parse(org_string, recognized_todo_keywords={'TODO', 'DONE'}):
    """ Parse an org mode document. """

    header_re = re.compile(r"^(\*+)\s(.*?)\s*$")
    tag_re = re.compile(r":([^ ]+?:)+?$")
    directive_re = re.compile(r"#\+(\w+)(:.*)?$")
    priority_re = re.compile(r" \[#([A-Z])\]")
    drawer_re = re.compile(r"^:(\w+?):\s*?$")
    drawer_child_re = re.compile(r"^:(\w+?):\s*?(.+)$")
    header_stack = []
    document = []
    open_drawer = None
    for line in org_string.split('\n'):

        header_match = None
        directive_match = None
        header_match = re.match(header_re, line)
        directive_match = re.match(directive_re, line)
        drawer_match = re.match(drawer_re, line)
        drawer_child_match = re.match(drawer_child_re, line)

        current_header = peek(header_stack)
        if drawer_match:
            # end of drawer?
            if line == ':END:':
                if current_header is not None:
                    # push the drawer to the current_header
                    current_header.children.append(open_drawer)
                else:
                    # push the drawer to the root document
                    document.append(open_drawer)
                open_drawer = None
            else:
                # drawer is not ending, therefore start a new one.
                open_drawer = Drawer(drawer_match.group(1))
        elif open_drawer is not None and drawer_child_match:
            # push property to open drawer
            open_drawer.children.append((drawer_child_match.group(1),
                                         drawer_child_match.group(2).strip()))
        elif header_match:
            # parse and append header
            # count '*' and set the level to that number
            level = len(header_match.group(1))
            header = Header(level, "", [])
            # take everything after '*** '
            text = header_match.group(2)
            tags = re.search(tag_re, text)
            todo = None
            priority = None
            if tags:
                # extract tags from text, and then trim heading text
                tags_list = tags.group(0).split(':')[1:-1]
                header.set_tags(tags_list)
                (start_match, _) = tags.span()
                text = text[:start_match].strip()
            # look at first word of text
            todo_keyword = first_word(text)
            if todo_keyword in recognized_todo_keywords:
                # we recognize the first word as a todo keyword
                todo = todo_keyword
                # remove the keyword from heading text
                text = text[len(todo) + 1:]
                # attempt to find a priority
                priority_match = re.match(priority_re, text)
                if priority_match:
                    priority = priority_match.groups(1)
                    (_, end_match) = priority_match.span()
                    # strip priority from heading text
                    text = text[end_match + 1:]
            header.priority = priority
            header.todo = todo
            # parse inline markup
            header.text = parse_markup(text)
            # below is the magic for dealing with
            # header hierarchy
            if current_header is None:
                # if the header stack is empty
                # just push the current header to the stack
                header_stack.append(header)
            elif header.level <= current_header.level:
                # if the newly parsed header supercedes the header
                # at the top of the stack

                # pop the current header off the stack
                top_header = header_stack.pop()
                # continue popping headers off the stack until we reach a header of equal
                # or greater precendence
                while header.level <= top_header.level and header_stack != []:
                    top_header = header_stack.pop()
                # Push the popped header to the document
                document.append(top_header)
                # Push new header to the header stack
                header_stack.append(header)
            else:
                # if the header is a sub heading of the top header
                # append the header to the children of top header
                current_header.children.append(header)
                # push the header to the stack
                header_stack.append(header)
        elif current_header is not None and line[:10] == 'SCHEDULED:':
            # set the current header's scheduled property
            current_header.scheduled = parse_date(line[10:])
        elif current_header is not None and line[:9] == 'DEADLINE:':
            # set the current header's deadline property
            current_header.deadline = parse_date(line[9:])
        elif directive_match:
            # if the current line is a directive
            name = directive_match.group(1)
            args = None
            # directive has arguments?
            if directive_match.lastindex == 2:
                args = directive_match.group(2)
            directive = Directive(name, args)
            if open_drawer:
                open_drawer.children.append(directive)
            elif current_header:
                current_header.children.append(directive)
            else:
                document.append(directive)
        else:
            # plain and simple line
            markup = parse_markup(line)

            if open_drawer:
                open_drawer.children.append(markup)
            elif current_header:
                current_header.children.append(markup)
            else:
                document.append(markup)
    # Push dangling stack elements to document
    document += header_stack
    return document
