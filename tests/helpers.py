"""All text in this test suite is synthetic; none is empirical evidence."""
from style_compiler.contracts import Context, Document, Leakage, Provenance


def document(text="甲方提出方案。乙方提出疑问。双方核对条件。", identifier="synthetic-1", **kwargs):
    provenance = Provenance("synthetic_test", "synthetic-unit-tests", "synthetic unit-test fixture", True, True,
                            author_id="fixture-author-" + identifier, provenance_verified=True)
    defaults = dict(document_id=identifier, text=text,
                    context=Context("zh-Hans", "synthetic_test", "synthetic_test", "synthetic_test"),
                    provenance=provenance,
                    leakage=Leakage(identifier, identifier, identifier, identifier,
                                    "fixture-prompt-" + identifier))
    return Document(**(defaults | kwargs))
