"""
Azure Functions (Blob Trigger) Harmonizer for DIDI Platform.
Target deployment script for Microsoft Azure AI Foundry migration.
Triggered when a raw JSON is uploaded to container 'raw-articles'.
"""

import json
import logging
import azure.functions as func

app = func.FunctionApp()


@app.blob_trigger(
    arg_name="myblob",
    path="raw-articles/{name}",
    connection="AzureWebJobsStorage"
)
@app.blob_output(
    arg_name="outputblob",
    path="harmonized-articles/{name}",
    connection="AzureWebJobsStorage"
)
def didi_blob_harmonizer(myblob: func.InputStream, outputblob: func.Out[str]):
    logging.info(f"Azure Blob trigger processed: {myblob.name} ({myblob.length} bytes)")

    try:
        raw_data = json.loads(myblob.read().decode("utf-8"))
        url = raw_data.get("url", "")
        lang = raw_data.get("language") or ("it" if "/it/" in url else "de")

        harmonized_record = {
            "id": f"azure_{lang}_{myblob.name.split('/')[-1].replace('.json', '')}",
            "source": raw_data.get("source", "salto"),
            "language": lang,
            "url": url,
            "title": raw_data.get("title", ""),
            "publish_date": raw_data.get("publish_date", ""),
            "author": raw_data.get("author", "Redaktion"),
            "category": raw_data.get("category", "News"),
            "full_text": raw_data.get("full_text", ""),
            "word_count": len(raw_data.get("full_text", "").split()),
            "metadata": raw_data.get("metadata", {}),
        }

        outputblob.set(json.dumps(harmonized_record, ensure_ascii=False))
        logging.info(f"Harmonized article saved to container 'harmonized-articles'")
    except Exception as e:
        logging.error(f"Error harmonizing blob: {e}")
