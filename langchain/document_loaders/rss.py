"""Loader that fetches a sitemap and loads those URLs."""
import re
import itertools
from typing import Any, Callable, List, Optional, Generator

from langchain.document_loaders.web_base import WebBaseLoader
from langchain.schema import Document

from lxml import etree


def _default_parsing_function_text(content: Any) -> str:
    text = ""
    if "content" in content:
        text = content["content"]
    elif "description" in content:
        text = content["description"]

    return text


def _default_parsing_function_meta(meta: Any) -> str:
    r_meta = dict(meta)
    if "content" in r_meta:
        del r_meta["content"]
    
    if "description" in r_meta:
        del r_meta["description"]

    return r_meta

class RssLoader(WebBaseLoader):
    """Loader that fetches a sitemap and loads those URLs."""

    def __init__(
        self,
        web_path: str,
        parsing_function_text: Optional[Callable] = None,
        parsing_function_meta: Optional[Callable] = None,
    ):
        """Initialize with webpage path and optional filter URLs.

        Args:
            web_path: url of the sitemap
            filter_urls: list of strings or regexes that will be applied to filter the
                urls that are parsed and loaded
            parsing_function: Function to parse bs4.Soup output
        """

        try:
            import lxml  # noqa:F401
        except ImportError:
            raise ValueError(
                "lxml package not found, please install it with " "`pip install lxml`"
            )

        super().__init__(
            web_path,
            header_template=header_template,
        )

        self.parsing_function_text = parsing_function_text or _default_parsing_function_text
        self.parsing_function_meta = parsing_function_meta or _default_parsing_function_meta

        self.namespaces = {
            'content': 'http://purl.org/rss/1.0/modules/content/', 
            'dc':'http://purl.org/dc/elements/1.1/'
        }
        self.fields = [
                {"tag": "./link", "field":"source"}, 
                {"tag": "./title", "field":"title"}, 
                {"tag": "./category", "field": "category", "multi": True}, 
                {"tag": "./pubDate", "field":"publication_date"}, 
                {"tag": "./dc:creator", "field": "author"}, 
                {"tag": "./description", "field": "description", "type":"html"}, 
                {"tag": "./content:encoded", "field":"content", "type":"html"},
            ]
        self.items_selector = './channel/item'

    def parse_rss(self, root: Any) -> Generator[List[dict], None, None]:
        """Parse rss xml and load into a list of dicts."""

        for item in root.findall(self.items_selector):
            meta = {}
            for field in self.fields:
                element_list = item.findall(field["tag"],  namespaces=self.namespaces)
                for element in element_list:
                    text = element.text

                    if "type" in field and field["type"] == "html":
                        soup = BeautifulSoup(text,"html.parser")
                        text = soup.get_text()

                    if field["field"] not in meta:
                        meta[field["field"]] = [] if "multi" in field and field["multi"] ==True else ""
                    
                    if "multi" in field and field["multi"] ==True:
                        meta[field["field"]] = meta[field["field"]] if "field" in field else []
                        meta[field["field"]].append(text)
                    else:
                        meta[field["field"]] = text

            yield meta



    def load(self) -> List[Document]:
        """Load feeds."""
        
        docs: List[Document] = list()
        for feed in self.web_paths:
            xml = self.session.get(feed)
            root = etree.fromstring(xml)

            for item in self.parse_rss(root):
                text = self.parsing_function_text(item)
                metadata = self.parsing_function_meta(item)

                docs.append(Document(page_content=text, metadata=metadata))

        return docs