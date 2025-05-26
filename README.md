# Forbidden Words Checker

Een Node.js/Express webservice die documenten controleert op verboden woorden.

## Functionaliteit

Deze service biedt:
- Een `/upload` endpoint dat .docx en .pdf bestanden accepteert
- Controle op verboden woorden in het document
- Gedetailleerde rapportage met context, reden en aanbevelingen

## Installatie

```bash
# Installeer dependencies
npm install
```

## Gebruik

```bash
# Start de server
npm start
```

De server draait standaard op poort 3000. Je kunt een andere poort configureren door een PORT environment variable in te stellen.

### Endpoints

- `POST /upload` - Upload een .docx of .pdf bestand voor controle
- `GET /health` - Health check endpoint

## Deployment op Render

### Methode 1: Deployment via GitHub

1. Push je code naar een GitHub repository
2. Log in op je Render account: https://dashboard.render.com/
3. Klik op "New" en selecteer "Web Service"
4. Verbind met je GitHub repository
5. Vul de volgende instellingen in:
   - **Name**: forbidden-words-checker (of een andere naam naar keuze)
   - **Environment**: Node
   - **Region**: Frankfurt (EU Central) voor betere prestaties in Europa
   - **Branch**: main (of de branch die je wilt deployen)
   - **Build Command**: `npm install`
   - **Start Command**: `npm start`
   - **Plan**: Free (of een ander plan naar keuze)

6. Klik op "Create Web Service"

### Methode 2: Deployment via render.yaml

Deze repository bevat een `render.yaml` bestand dat automatisch de juiste configuratie instelt:

1. Push je code naar een GitHub repository
2. Log in op je Render account: https://dashboard.render.com/
3. Klik op "New" en selecteer "Blueprint"
4. Verbind met je GitHub repository
5. Render zal automatisch de configuratie uit render.yaml gebruiken
6. Controleer de instellingen en klik op "Apply"

### Belangrijke aandachtspunten voor een probleemloze deployment

- Zorg dat je de juiste Node.js versie gebruikt (18.x)
- Alle dependencies moeten correct gespecificeerd zijn in package.json
- De uploads directory wordt automatisch aangemaakt als deze niet bestaat
- De server luistert op alle interfaces (0.0.0.0) voor compatibiliteit met Render
- Controleer de logs in het Render dashboard als er problemen zijn

## Environment Variables

- `PORT` - De poort waarop de server draait (standaard: 3000)

## Technische Details

- Node.js/Express voor de server
- Multer voor bestandsuploads
- Axios voor API-requests
- Controleert op verboden woorden in Nederlands en Engels
- Genereert Markdown-tabellen met resultaten
