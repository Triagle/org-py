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
    def __init__(self, level, children):
        self.level = level
        self.children = children

class Drawer(Node):
    def __init__(self, name):
        self.name = name
        self.children = []
    def __repr__(self):
        return "{}: {}".format(self.name, self.children)
class Header(Node):
    """ Header node. """

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

class Directive():
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
    def __init__(self, style, text):
        self.style = style
        self.text = text
    def __repr__(self):
        surround = char_for_style(self.style)
        return "{0}{1}{0}".format(surround, self.text)

class Link():
    def __init__(self, url, text):
        self.url = url
        self.text = text
    def __repr__(self):
        return '[[{}][{}]]'.format(self.url, self.text)
class Markup(Node):
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
    date_re = re.compile(r"<(\d{4})-(\d{2})-(\d{2}) .+?>")
    date = date.strip()
    date_match = re.match(date_re, date)
    if date_match:
        year = date_match.group(1)
        month = date_match.group(2)
        day = date_match.group(3)
        return datetime.date(year, month, day)
    else:
        return None

    
def parse_markup(string):
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
        directive_match = False
        header_match = re.match(header_re, line)
        directive_match = re.match(directive_re, line)
        drawer_match = re.match(drawer_re, line)
        drawer_child_match = re.match(drawer_child_re, line)

        current_header = peek(header_stack)
        if drawer_match:
            if line == ':END:':
                if current_header is not None:
                    current_header.children.append(open_drawer)
                else:
                    document.append(open_drawer)
                open_drawer = None
            else:
                open_drawer = Drawer(drawer_match.group(1))
        elif open_drawer is not None and drawer_child_match:
            open_drawer.children.append((drawer_child_match.group(1),
                                         drawer_child_match.group(2).strip()))
        elif header_match:
            level = len(header_match.group(1))
            header = Header(level, "", [])
            text = header_match.group(2)
            tags = re.search(tag_re, text)
            todo = None
            priority = None
            if tags:
                header.set_tags(tags.group(0).split(':')[1:-1])
                (start_match, _) = tags.span()
                text = text[:start_match].strip()
            todo_keyword = first_word(text)
            if todo_keyword in recognized_todo_keywords:
                todo = todo_keyword
                text = text[len(todo) + 1:]
                priority_match = re.match(priority_re, text)
                if priority_match:
                    priority = priority_match.groups(1)
                    (_, end_match) = priority_match.span()
                    text = text[end_match + 1:]
            header.priority = priority
            header.todo = todo
            header.text = parse_markup(text)
            if current_header is None:
                header_stack.append(header)
            elif header.level <= current_header.level:
                top_header = header_stack.pop()
                while header.level <= top_header.level and header_stack != []:
                    top_header = header_stack.pop()
                document.append(top_header)
                header_stack.append(header)
            else:
                current_header.children.append(header)
                header_stack.append(header)
        elif current_header is not None and line[:10] == 'SCHEDULED:':
            current_header.scheduled = parse_date(line[10:])
        elif current_header is not None and line[:9] == 'DEADLINE:':
            current_header.deadline = parse_date(line[9:])
        elif directive_match:
            name = directive_match.group(1)
            args = None
            if directive_match.lastindex() == 2:
                args = directive_match.group(2)
            directive = Directive(name, args)
            if open_drawer:
                open_drawer.children.append(directive)
            elif current_header:
                current_header.children.append(directive)
            else:
                document.append(directive)
        else:
            markup = parse_markup(line)

            if open_drawer:
                open_drawer.children.append(markup)
            elif current_header:
                current_header.children.append(markup)
            else:
                document.append(markup)

    if len(header_stack) > 0:
        document += header_stack
    return document
