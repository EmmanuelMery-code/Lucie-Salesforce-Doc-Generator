# Prompt : ajouter Ollama (LLM local) comme troisieme fournisseur IA de Lucie

Ce document est un **prompt pret a l'emploi** a coller dans un agent IA
(Cursor, Claude Code, etc.) pour demander l'ajout du support **Ollama** dans
l'onglet Discussion de Lucie. Il decrit le but, le contexte technique exact,
la specification, les contraintes et les tests d'acceptation. L'agent doit
pouvoir executer la tache sans devoir explorer davantage le projet.

> **Date de redaction :** 2026-04-24
> **Auteur initial :** Emmanuel Mery
> **Motivation :** s'affranchir definitivement des quotas gratuits
> Gemini / Claude en executant un modele localement. Aucun cout, aucune cle
> API, aucune limite de requetes.

---

## 1. Objectif

Ajouter un troisieme fournisseur IA nomme **`Ollama`** a cote des fournisseurs
actuels `Gemini` et `Claude`, disponible dans :

- le combobox `Configuration > Discussion > Fournisseur IA`
- la meme mecanique de chat/thread/retry que les deux autres fournisseurs
- la persistance dans `app_settings.json`

Ollama tourne **en local** (daemon `ollama serve`, API HTTP
`http://localhost:11434`) : aucune cle API, aucun quota, aucune connectivite
Internet requise une fois le modele telecharge.

---

## 2. Contexte technique (etat actuel du code)

### 2.1 Architecture IA

Fichier cle : **`src/ai/ai_service.py`**. Il definit :

- `class AIServiceBase` : base abstraite avec attributs `name`, `default_model`,
  `available_models`, methode `chat(messages, system_prompt, max_tokens, *, on_retry, max_retries)`.
- `class ClaudeService(AIServiceBase)` : utilise le package `anthropic`.
- `class GeminiService(AIServiceBase)` : utilise `google.generativeai`.
- `def create_service(provider, settings) -> AIServiceBase` : factory qui
  construit le bon service selon la valeur `"gemini"` / `"claude"`.
- `def _call_with_retry(callable_, *, provider_label, on_retry, max_retries)` :
  wrapper de retry pour les erreurs 429. **A reutiliser** pour Ollama, meme si
  Ollama ne renvoie pas de 429, car il protege aussi contre d'autres erreurs
  transitoires.
- Constantes `GEMINI_MODELS` et `CLAUDE_MODELS` (listes de modeles).
- Exception `DailyQuotaExceeded` : non applicable a Ollama.

Fichier d'export : **`src/ai/__init__.py`** : re-exporte
`create_service`, `GEMINI_MODELS`, `CLAUDE_MODELS`, etc.

Fichier UI : **`src/ui/application.py`**. Points cles a modifier :

- Liste `AI_PROVIDERS` importee depuis `src/ui/constants.py`.
- `__init__` charge `self.claude_api_key_var`, `self.gemini_api_key_var`,
  `self.claude_model_var`, `self.gemini_model_var` et leurs valeurs par
  defaut (`DEFAULT_CLAUDE_MODEL`, `DEFAULT_GEMINI_MODEL`).
- Methode `_build_configuration_discussion_tab(parent, edit_vars)` construit
  l'UI avec les combos `configuration_claude_model` et
  `configuration_gemini_model` via `_config_combo_row`. **Ajouter un combo
  Ollama au meme endroit.**
- Methode `_send_discussion_message` prepare `settings_for_service` puis
  appelle `create_service(provider, settings_for_service)`.
- Persistance : methode `_save_settings` ecrit `claude_model`, `gemini_model`,
  etc., dans `app_settings.json`. **Ajouter `ollama_model` et
  `ollama_base_url`.**
- Traductions : **`src/ui/translations.py`**. Les deux dictionnaires `fr` et
  `en` contiennent les cles `configuration_claude_model`,
  `configuration_gemini_model`. Ajouter `configuration_ollama_model`,
  `configuration_ollama_base_url`, `configuration_ollama_description`,
  `configuration_ollama_unreachable`.
- Constante : **`src/ui/constants.py`** contient
  `AI_PROVIDERS = ["Gemini", "Claude"]`. **Ajouter `"Ollama"`** et conserver
  Gemini en tete pour ne pas changer le provider par defaut des utilisateurs
  existants.

### 2.2 Format de messages

Chaque service recoit une liste `list[AIMessage]`. `AIMessage` est un
`dataclass(slots=True)` avec `role` (`"user"` ou `"assistant"`) et `content`.
Le service prepend un **system prompt** separement.

### 2.3 Context builder

**`src/ai/context_builder.py`** construit `build_org_context(snapshot)` : un
texte plat de quelques Ko decrivant l'org analysee. Il est concatene au
system_prompt, separement du chat. **Rien a changer.**

---

## 3. Specification fonctionnelle

### 3.1 Nouveau fournisseur `Ollama`

- Nom affiche dans l'UI : `Ollama`.
- Valeur interne (`provider_norm` dans `create_service`) : `"ollama"`.
- Parametres utilisateur :
  - **Modele** (texte libre ET combobox prerempli, cf. 3.3) : defaut
    `llama3.1:8b`.
  - **URL du serveur** : defaut `http://localhost:11434`.
  - **Pas de cle API** (les deux champs cle Claude/Gemini restent inchanges).

### 3.2 Communication avec Ollama

Utiliser le package Python officiel **`ollama`** (`pip install ollama`). Si
non installe, lever `AIProviderNotInstalled` avec un message expliquant
`pip install ollama` **et** un renvoi vers <https://ollama.com/download> pour
installer le daemon. Exemple d'appel :

```python
import ollama  # type: ignore
client = ollama.Client(host=base_url)
response = client.chat(
    model=self.model,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "..."},
    ],
    options={"num_predict": max_tokens},
)
text = response["message"]["content"]
```

Si le daemon Ollama n'est pas en ecoute, le SDK leve
`httpx.ConnectError` ou `ollama.ResponseError`. Dans ce cas **lever une
exception personnalisee `OllamaUnreachable(AIProviderNotConfigured)`** avec
un message clair demandant de lancer `ollama serve` et verifier que l'URL
`http://localhost:11434` est joignable. Ne **pas** faire de retry : l'erreur
ne se resoudra pas toute seule.

### 3.3 Liste de modeles

- Predefinir une petite liste courante dans `ai_service.py` :
  ```python
  OLLAMA_DEFAULT_MODELS: list[str] = [
      "llama3.1:8b",
      "llama3.2:3b",
      "mistral:7b",
      "qwen2.5:7b",
      "phi3:3.8b",
      "gemma2:9b",
      "codellama:7b",
  ]
  ```
- **En plus**, fournir un bouton `Rafraichir la liste` dans l'UI qui
  appelle `GET {base_url}/api/tags` via le SDK (`client.list()`) et
  remplace la liste du combobox par les modeles reellement installes
  localement. Si l'appel echoue, conserver la liste par defaut et ajouter
  un log `configuration_ollama_unreachable`.

### 3.4 Comportement UI

Dans l'onglet `Configuration > Discussion`, apres la section Gemini, ajouter :

```
Modele Ollama          [combobox editable][ bouton Refresh ]
URL serveur Ollama     [entry http://localhost:11434     ]
```

Si `AI_PROVIDERS` contient `"Ollama"` mais que le provider selectionne est
`Ollama` et que la cle "kind" n'a pas de sens, **ne pas** exiger de cle.
Dans `_send_discussion_message`, remplacer la verification actuelle
`key_var = self.claude_api_key_var if provider == "Claude" else ...` par un
test explicite a trois branches : `Claude`, `Gemini`, `Ollama`. Pour Ollama,
**ne pas** verifier de cle ; a la place, verifier que `self.ollama_base_url_var`
n'est pas vide.

Ajouter deux handlers de queue si necessaire : `ollama_models_loaded` /
`ollama_models_error` pour le refresh asynchrone (similaire a
`discussion_info`).

### 3.5 Persistance

Dans `_save_settings`, ajouter :

```python
"ollama_model": self.ollama_model_var.get().strip() or self.DEFAULT_OLLAMA_MODEL,
"ollama_base_url": self.ollama_base_url_var.get().strip() or self.DEFAULT_OLLAMA_BASE_URL,
```

Dans `__init__`, charger ces valeurs avec fallback. Si la cle n'existe pas
dans `app_settings.json`, prendre les valeurs par defaut.

### 3.6 Factory

Dans `create_service` :

```python
if provider_norm == "ollama":
    return OllamaService(
        base_url=str(settings.get("ollama_base_url", "") or "") or None,
        model=str(settings.get("ollama_model", "") or "") or None,
    )
```

Signature de `OllamaService.__init__(base_url: str | None = None, model: str | None = None)`.
**Surcharger `is_ready`** pour renvoyer `True` tant que `base_url` est defini,
puisque l'absence de cle API n'est pas un critere. Le pattern
`AIProviderNotConfigured` est reserve au cas ou l'URL est vide ou
syntaxiquement invalide.

---

## 4. Contraintes a respecter

1. **Langue** : toutes les traductions et messages doivent exister en
   **francais ET anglais** (`src/ui/translations.py`). Le ton reste sobre,
   sans emoji.
2. **Pas de dependance obligatoire** : si le package `ollama` n'est pas
   installe, l'application doit **continuer a fonctionner** avec Gemini et
   Claude. Ne pas faire `from ollama import ...` au niveau module.
3. **Pas de modification destructrice** : ne **jamais** supprimer les
   fournisseurs existants, ni les modeles Gemini/Claude, ni les cles
   `claude_api_key`, `gemini_api_key`, `claude_model`, `gemini_model` dans
   `app_settings.json`.
4. **Compatibilite settings** : un `app_settings.json` existant sans cle
   `ollama_*` doit charger proprement et tomber sur les defauts.
5. **Aucun emoji** dans le code ou les messages UI.
6. **Pas de retry automatique** sur Ollama (pas de 429 par nature). Si
   `httpx.ConnectError`, lever immediatement `OllamaUnreachable`.
7. **Threading** : reutiliser le `Thread` worker existant dans
   `_send_discussion_message`. Ollama peut etre lent sur CPU, ne pas
   bloquer l'UI.

---

## 5. Plan d'implementation pas a pas

1. **`src/ai/ai_service.py`**
   1. Ajouter `OLLAMA_DEFAULT_MODELS: list[str]`.
   2. Definir `class OllamaUnreachable(AIProviderNotConfigured)`.
   3. Definir `class OllamaService(AIServiceBase)` avec `name = "Ollama"`,
      `default_model = "llama3.1:8b"`, attribut `base_url`,
      methode `chat(...)` et methode `list_local_models() -> list[str]`.
   4. Etendre `create_service` avec la branche `"ollama"`.
2. **`src/ai/__init__.py`** : re-exporter
   `OLLAMA_DEFAULT_MODELS`, `OllamaService`, `OllamaUnreachable`.
3. **`src/ui/constants.py`** : `AI_PROVIDERS = ["Gemini", "Claude", "Ollama"]`.
4. **`src/ui/translations.py`** : ajouter les cles fr + en
   (`configuration_ollama_model`, `configuration_ollama_base_url`,
   `configuration_ollama_refresh`, `configuration_ollama_description`,
   `configuration_ollama_unreachable`, `configuration_ollama_section`,
   `discussion_ollama_local_hint`).
5. **`src/ui/application.py`**
   1. Importer `OLLAMA_DEFAULT_MODELS`, `OllamaUnreachable`.
   2. Ajouter `DEFAULT_OLLAMA_MODEL`, `DEFAULT_OLLAMA_BASE_URL`,
      `OLLAMA_MODEL_CHOICES` en attributs de classe.
   3. Dans `__init__`, ajouter `self.ollama_model_var` et
      `self.ollama_base_url_var` avec fallback defaut, plus migration
      silencieuse si l'ancienne valeur contient un modele inconnu.
   4. Dans `edit_vars` de la fenetre de configuration, ajouter
      `ollama_model` et `ollama_base_url`.
   5. Dans `_build_configuration_discussion_tab`, ajouter la section
      Ollama avec : combo modele, entry URL, bouton `Refresh`, label
      d'astuce traduit.
   6. Dans `_apply_configuration_changes`, persister les deux nouvelles
      valeurs dans les StringVar de l'instance.
   7. Dans `_save_settings`, ajouter les cles `ollama_model` et
      `ollama_base_url`.
   8. Dans `_send_discussion_message`, elargir `settings_for_service` avec
      `ollama_model` et `ollama_base_url`, et adapter la verification
      de cle (branche explicite pour `Ollama`).
   9. Ajouter un handler pour l'evenement `ollama_models_loaded` /
      `ollama_models_error` dans `_poll_queue`.
6. **Tests** (smoke test dans `_smoke_ollama.py`, supprime en fin de tache)
   1. Instancier `OllamaService(base_url="http://localhost:11434")`.
   2. Appeler `list_local_models()` avec un daemon lance : doit retourner
      au moins un modele sous forme `list[str]`.
   3. Appeler `chat(...)` avec un court prompt et assertionner que le
      retour est une str non vide.
   4. Tester `OllamaService(base_url="http://127.0.0.1:9")` (port
      non-ecoute) : doit lever `OllamaUnreachable` avec un message clair
      et **sans retry**.
   5. Supprimer `_smoke_ollama.py` apres verification.

---

## 6. Tests d'acceptation

- [ ] `python -c "from src.ai import OllamaService; print(OllamaService.default_model)"` imprime `llama3.1:8b`.
- [ ] `AI_PROVIDERS` contient `"Ollama"` dans l'ordre `["Gemini", "Claude", "Ollama"]`.
- [ ] Lancer l'app sans package `ollama` installe ne provoque **aucune**
      erreur au demarrage ; seule la tentative d'envoyer un message via
      Ollama leve `AIProviderNotInstalled`.
- [ ] Choisir `Ollama` dans `Configuration > Discussion`, saisir un modele
      installe, cliquer `Refresh` avec le daemon actif : la liste
      se met a jour.
- [ ] Envoyer un message avec Ollama : la reponse s'affiche, **sans
      quota**, **sans retry**, **sans cle API**.
- [ ] Stopper le daemon (`ollama serve`) et re-envoyer un message :
      l'erreur UI doit citer explicitement `http://localhost:11434` et
      proposer de lancer `ollama serve`. Aucun retry silencieux.
- [ ] Relancer l'app apres avoir configure Ollama : la valeur du modele
      et de l'URL sont persistees.
- [ ] Basculer le fournisseur sur `Claude` ou `Gemini` : tout fonctionne
      comme avant (non-regression).
- [ ] `ReadLints` ne remonte aucune erreur sur les fichiers modifies.
- [ ] Aucun emoji introduit dans le code ou les messages.

---

## 7. Pieges connus

1. **Dependance optionnelle** : `import ollama` **doit** etre dans le corps
   de la methode `chat` / `list_local_models`, pas au niveau module. Sinon
   les utilisateurs sans Ollama voient l'app planter au demarrage.
2. **Tag de modele** : Ollama distingue `llama3.1` (equivaut a `:latest`) de
   `llama3.1:8b`. Garder le tag complet pour eviter les surprises de quota
   memoire.
3. **Prompt systeme** : certains modeles (ex. `llama3.1:8b`) ignorent
   partiellement les messages `role="system"` si le prompt est enorme. Le
   context builder actuel peut produire 10-20 Ko de contexte ; c'est OK
   avec un modele 8B, lent sur CPU pur, acceptable sur GPU 8 Go VRAM.
4. **Encoding** : le SDK renvoie du texte UTF-8 ; ne **pas** passer par
   `str.encode()` ni faire de replace/sanitation.
5. **Time-out** : par defaut le client Ollama ne pose pas de time-out HTTP.
   Sur CPU avec un modele 8B et un gros contexte, une generation peut
   depasser 2 minutes. **Ne pas** mettre de time-out cote Lucie, le worker
   tourne deja dans un Thread daemon qui ne bloque pas l'UI.
6. **Streaming** : le SDK supporte `stream=True`. **Ne pas l'utiliser** dans
   la v1 ; rester sur une reponse bloquante pour garder la meme boucle de
   file d'attente que Claude et Gemini.
7. **Modeles distants** : Ollama peut etre deporte sur une autre machine du
   LAN (`http://192.168.x.x:11434`). C'est l'interet du champ URL serveur.
   Ne pas forcer `localhost`.

---

## 8. Resultat attendu

Apres implementation, l'utilisateur doit pouvoir :

1. Installer Ollama (`https://ollama.com/download`) et lancer
   `ollama pull llama3.1:8b` une fois.
2. Ouvrir Lucie, aller dans `Configuration > Discussion`, choisir
   `Ollama` comme fournisseur, laisser l'URL par defaut, sauvegarder.
3. Utiliser la discussion sans **aucune** limite de quota, sans Internet,
   sans cle API.
4. Pouvoir revenir a Gemini ou Claude a tout moment sans perte de config.
