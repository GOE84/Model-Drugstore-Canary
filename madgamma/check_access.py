from huggingface_hub import model_info
from huggingface_hub.utils import RepositoryNotFoundError, GatedRepoError

model_id = "google/medgemma-4b-it"

try:
    info = model_info(model_id)
    print(f"Access granted to {model_id}")
except GatedRepoError:
    print(f"Access DENIED to {model_id}. Please accept terms at https://huggingface.co/{model_id}")
except RepositoryNotFoundError:
    print(f"Model {model_id} not found.")
except Exception as e:
    print(f"An error occurred: {e}")
