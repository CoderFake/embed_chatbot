"""Generate graph visualization."""
from services.chat.graph import chat_graph


def main() -> None:
    mermaid = chat_graph.get_graph().draw_mermaid()
    print("=== Graph Visualization (Mermaid) ===")
    print(mermaid)
    with open("docs/chat_graph.mmd", "w", encoding="utf-8") as file:
        file.write(mermaid)
    print("\nSaved to docs/chat_graph.mmd")


if __name__ == "__main__":
    main()
