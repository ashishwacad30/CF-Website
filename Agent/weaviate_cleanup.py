import os
import sys
import argparse
from dotenv import load_dotenv, find_dotenv
from weaviate import Client as V3Client  # v3 client
from weaviate.auth import AuthApiKey

def connect_v3(url: str, api_key: str | None) -> V3Client:
    if api_key:
        return V3Client(url=url, auth_client_secret=AuthApiKey(api_key))
    return V3Client(url=url)

def class_exists(client: V3Client, class_name: str) -> bool:
    try:
        schema = client.schema.get()
        return any(c.get("class") == class_name for c in schema.get("classes", []) )
    except Exception:
        return False

def drop_class(client: V3Client, class_name: str) -> None:
    if class_exists(client, class_name):
        client.schema.delete_class(class_name)

def recreate_class(client: V3Client, class_name: str) -> None:
    client.schema.create_class({
        "class": class_name,
        "vectorizer": "none",
        "properties": [
            {"name": "text", "dataType": ["text"]},
            {"name": "page", "dataType": ["int"]},
            {"name": "product_code", "dataType": ["text"]},
            {"name": "category", "dataType": ["text"]},
            {"name": "source", "dataType": ["text"]},
            {"name": "recursive_idx", "dataType": ["int"]},
        ],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete embeddings in Weaviate (v3 client)")
    parser.add_argument("--drop-class", action="store_true", help="Drop the entire class (deletes all objects)")
    parser.add_argument("--recreate", action="store_true", help="Recreate the class after dropping it")
    parser.add_argument("--class-name", default=None, help="Override class name (defaults to WEAVIATE_CLASS_NAME)")
    parser.add_argument("--host", default=None, help="Override host URL (defaults to WEAVIATE_HOST)")
    args = parser.parse_args()

    load_dotenv(find_dotenv())

    host = args.host or os.getenv("WEAVIATE_HOST", "http://localhost:8080")
    api_key = os.getenv("WEAVIATE_API_KEY") or None
    class_name = args.class_name or os.getenv("WEAVIATE_CLASS_NAME", "ProductChunk")

    client = connect_v3(host, api_key)

    if args.drop_class:
        if not class_exists(client, class_name):
            print(f"Class '{class_name}' does not exist; nothing to drop.")
        else:
            print(f"Dropping class '{class_name}' …")
            drop_class(client, class_name)
            print("Dropped.")
        if args.recreate:
            print(f"Recreating class '{class_name}' …")
            recreate_class(client, class_name)
            print("Recreated.")
        return 0

    # Default behavior: delete all objects by dropping class to ensure clean removal
    if class_exists(client, class_name):
        print(f"Deleting all embeddings by dropping class '{class_name}' …")
        drop_class(client, class_name)
        print("Deleted.")
        print("Tip: run with --recreate to recreate the schema automatically.")
    else:
        print(f"Class '{class_name}' does not exist; nothing to delete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


