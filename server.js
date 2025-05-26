const express = require('express');
const multer = require('multer');
const axios = require('axios');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const FormData = require('form-data');
const mammoth = require('mammoth');
const pdfParse = require('pdf-parse');

// Initialize Express app
const app = express();
const PORT = process.env.PORT || 3000;

// Configure CORS with more permissive settings
app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Handle preflight requests
app.options('*', cors());

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static files from the public directory
app.use(express.static(path.join(__dirname, 'public')));

// Configure Multer for file uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(__dirname, 'uploads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir);
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    cb(null, `${Date.now()}-${file.originalname}`);
  }
});

// File filter to only accept .docx and .pdf files
const fileFilter = (req, file, cb) => {
  const allowedMimeTypes = ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/pdf'];
  const allowedExtensions = ['.docx', '.pdf'];
  
  const fileExtension = path.extname(file.originalname).toLowerCase();
  
  if (allowedMimeTypes.includes(file.mimetype) && allowedExtensions.includes(fileExtension)) {
    cb(null, true);
  } else {
    cb(new Error('Invalid file type. Only .docx and .pdf files are allowed.'), false);
  }
};

const upload = multer({ 
  storage: storage,
  fileFilter: fileFilter,
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB limit
});

// Forbidden words database
const forbiddenWords = {
  "assurance-woorden": {
    "title": "Assurance-woorden",
    "number": "1",
    "words": {
      "nl": ["garanderen", "verzekeren", "waarborgen", "verklaren", "bevestigen", "certificeren", "valideren"],
      "en": ["guarantee", "insure", "assure", "ensure", "warrant", "attest", "verify", "certify", "validate"]
    },
    "reason": "Deze woorden impliceren een hoog niveau van zekerheid dat niet past bij een pentest.",
    "recommendation": "Gebruik neutralere termen zoals 'observeren', 'constateren', 'identificeren' of 'vaststellen'."
  },
  "conclusies": {
    "title": "Conclusies",
    "number": "2",
    "words": {
      "nl": ["wij concluderen", "wij zijn van oordeel dat", "wij vinden dat", "wij hebben vastgesteld dat", "wij geloven", "u heeft… nageleefd", "ons is niets gebleken op grond waarvan wij zouden moeten concluderen dat…", "niets dat wij hebben gereviewd geeft een indicatie dat…", "gebaseerd op onze werkzaamheden hebben wij geen reden om aan te nemen dat…"],
      "en": ["we conclude", "we are of the opinion", "in our opinion", "we find", "we found", "we have determined", "we believe", "you comply with…", "nothing has come to our attention that causes us to believe…", "nothing we reviewed indicated…", "based on the procedures we performed, we have no reason to believe that…"]
    },
    "reason": "Deze formuleringen suggereren een definitieve conclusie of oordeel dat buiten de scope van een pentest valt.",
    "recommendation": "Gebruik feitelijke beschrijvingen van wat is geobserveerd, zonder een definitief oordeel te vellen."
  },
  "technische-termen": {
    "title": "Technische termen",
    "number": "3",
    "words": {
      "nl": ["controle", "beoordeling", "samenstellen"],
      "en": ["audit", "review", "compile"]
    },
    "reason": "Deze termen hebben specifieke technische betekenissen in assurance-contexten die verwarring kunnen veroorzaken.",
    "recommendation": "Gebruik specifiekere termen zoals 'pentest', 'security assessment', 'vulnerability scan', etc."
  },
  "absolute-bewoording": {
    "title": "Absolute bewoording",
    "number": "4",
    "words": {
      "nl": ["altijd", "nooit", "alle", "geen", "complete", "geheel"],
      "en": ["always", "never", "all", "none", "complete", "entire"]
    },
    "reason": "Absolute bewoordingen suggereren een volledigheid die zelden haalbaar is in pentesting.",
    "recommendation": "Gebruik nuancerende termen zoals 'tijdens onze tests', 'in de geteste componenten', etc."
  }
};

// Helper function to check if a word is in the forbidden list
function isForbiddenWord(word) {
  const normalizedWord = word.toLowerCase().trim();
  
  for (const category in forbiddenWords) {
    const categoryData = forbiddenWords[category];
    
    // Check Dutch words
    if (categoryData.words.nl.some(forbidden => 
      normalizedWord === forbidden.toLowerCase() || 
      normalizedWord.includes(forbidden.toLowerCase())
    )) {
      return {
        word: normalizedWord,
        category: category,
        title: categoryData.title,
        number: categoryData.number,
        reason: categoryData.reason,
        recommendation: categoryData.recommendation
      };
    }
    
    // Check English words
    if (categoryData.words.en.some(forbidden => 
      normalizedWord === forbidden.toLowerCase() || 
      normalizedWord.includes(forbidden.toLowerCase())
    )) {
      return {
        word: normalizedWord,
        category: category,
        title: categoryData.title,
        number: categoryData.number,
        reason: categoryData.reason,
        recommendation: categoryData.recommendation
      };
    }
  }
  
  return null;
}

// Function to extract text from documents
const extractTextFromDocument = async (filePath) => {
  const fileExtension = path.extname(filePath).toLowerCase();
  let textContent = [];
  
  try {
    if (fileExtension === '.docx') {
      // Extract text from DOCX using mammoth
      const result = await mammoth.extractRawText({ path: filePath });
      const text = result.value;
      
      // Simple page splitting - in a real implementation, you would need more sophisticated parsing
      // to accurately determine page numbers
      const pages = text.split('\n\n\n').filter(page => page.trim().length > 0);
      
      pages.forEach((pageContent, index) => {
        // Split page content into paragraphs
        const paragraphs = pageContent.split('\n\n').filter(para => para.trim().length > 0);
        
        paragraphs.forEach(paragraph => {
          if (paragraph.trim().length > 0) {
            textContent.push({
              page: index + 1,
              text: paragraph.trim()
            });
          }
        });
      });
    } else if (fileExtension === '.pdf') {
      // Extract text from PDF using pdf-parse
      const dataBuffer = fs.readFileSync(filePath);
      const data = await pdfParse(dataBuffer);
      
      // pdf-parse doesn't provide page numbers directly, so we need to estimate
      // In a real implementation, you would use a more sophisticated approach
      const pageTexts = data.text.split('\n\n\n').filter(page => page.trim().length > 0);
      
      pageTexts.forEach((pageContent, index) => {
        const paragraphs = pageContent.split('\n\n').filter(para => para.trim().length > 0);
        
        paragraphs.forEach(paragraph => {
          if (paragraph.trim().length > 0) {
            textContent.push({
              page: index + 1,
              text: paragraph.trim()
            });
          }
        });
      });
    }
    
    return textContent;
  } catch (error) {
    console.error('Error extracting text from document:', error);
    throw new Error(`Failed to extract text from ${fileExtension} document: ${error.message}`);
  }
};

// Function to scan text for forbidden words
const scanForForbiddenWords = (textContent) => {
  const results = [];
  
  // Process each text segment
  textContent.forEach(segment => {
    const { page, text } = segment;
    
    // Check against all categories of forbidden words
    for (const category in forbiddenWords) {
      const categoryData = forbiddenWords[category];
      
      // Check Dutch words
      categoryData.words.nl.forEach(forbiddenWord => {
        if (text.toLowerCase().includes(forbiddenWord.toLowerCase())) {
          results.push({
            word: forbiddenWord,
            page: page,
            context: text,
            title: `${categoryData.title} (${categoryData.number})`,
            reason: categoryData.reason,
            recommendation: categoryData.recommendation
          });
        }
      });
      
      // Check English words
      categoryData.words.en.forEach(forbiddenWord => {
        if (text.toLowerCase().includes(forbiddenWord.toLowerCase())) {
          results.push({
            word: forbiddenWord,
            page: page,
            context: text,
            title: `${categoryData.title} (${categoryData.number})`,
            reason: categoryData.reason,
            recommendation: categoryData.recommendation
          });
        }
      });
    }
  });
  
  return results;
};

// Check endpoint for direct document processing
app.post('/check', upload.single('file'), async (req, res) => {
  let filePath = null;
  
  try {
    console.log('Received request to /check endpoint');
    console.log('Request headers:', req.headers);
    console.log('Request body:', req.body);
    console.log('Request file:', req.file);
    
    if (!req.file) {
      console.error('No file uploaded or invalid file type');
      return res.status(400).json({ error: 'No file uploaded or invalid file type' });
    }

    filePath = req.file.path;
    console.log(`Processing file: ${filePath}`);
    
    // Verify file exists and is readable
    if (!fs.existsSync(filePath)) {
      console.error(`File not found at path: ${filePath}`);
      return res.status(400).json({ error: 'File upload failed - file not found' });
    }
    
    // Extract text from the document
    const textContent = await extractTextFromDocument(filePath);
    console.log(`Successfully extracted text from document, found ${textContent.length} text segments`);
    
    // If no text was extracted, return a specific error
    if (textContent.length === 0) {
      console.warn('No text content could be extracted from the document');
      return res.status(400).json({ 
        error: 'Document processing failed', 
        details: 'No text content could be extracted from the document. Please ensure the file is not corrupted or password protected.'
      });
    }
    
    // Scan for forbidden words
    const foundWords = scanForForbiddenWords(textContent);
    console.log(`Found ${foundWords.length} forbidden words in the document`);
    
    // Clean up the uploaded file
    try {
      fs.unlinkSync(filePath);
      console.log(`Successfully deleted temporary file: ${filePath}`);
    } catch (cleanupError) {
      console.warn(`Warning: Could not delete temporary file: ${filePath}`, cleanupError);
      // Continue processing even if cleanup fails
    }
    
    // Return the results
    if (foundWords.length === 0) {
      return res.json({
        message: "Er zijn geen verboden woorden aangetroffen in het document.",
        results: []
      });
    } else {
      return res.json(foundWords);
    }
    
  } catch (error) {
    console.error('Error processing file:', error);
    
    // Try to clean up the file if it exists
    if (filePath && fs.existsSync(filePath)) {
      try {
        fs.unlinkSync(filePath);
        console.log(`Cleaned up file after error: ${filePath}`);
      } catch (cleanupError) {
        console.warn(`Warning: Could not delete temporary file after error: ${filePath}`, cleanupError);
      }
    }
    
    res.status(500).json({ error: 'Internal server error', details: error.message });
  }
});

// Upload endpoint
app.post('/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded or invalid file type' });
    }

    const filePath = req.file.path;
    
    // Create form data for the API request
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    
    // Send the file to the Render API
    const response = await axios.post(
      'https://forbiddenwords-correct.onrender.com/check',
      formData,
      {
        headers: {
          ...formData.getHeaders(),
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity
      }
    );
    
    // Process the response from the API
    const foundWords = response.data;
    
    // If no forbidden words found
    if (!foundWords || foundWords.length === 0) {
      return res.json({ message: 'Er zijn geen verboden woorden aangetroffen in het document.' });
    }
    
    // Process and enhance the found words with additional information
    const enhancedResults = foundWords.map(item => {
      const forbiddenInfo = isForbiddenWord(item.word);
      
      return {
        word: item.word,
        page: item.page,
        context: item.context,
        title: forbiddenInfo ? `${forbiddenInfo.title} (${forbiddenInfo.number})` : 'Onbekend',
        reason: forbiddenInfo ? forbiddenInfo.reason : 'Onbekend',
        recommendation: forbiddenInfo ? forbiddenInfo.recommendation : 'Herformuleer of verwijder'
      };
    });
    
    // Generate Markdown table
    let markdownTable = '| Verboden woord | Pagina | Context | Titel & Nummer | Waarom verboden | Aanbeveling |\n';
    markdownTable += '|---------------|--------|---------|----------------|-----------------|-------------|\n';
    
    enhancedResults.forEach(result => {
      markdownTable += `| ${result.word} | ${result.page} | ${result.context} | ${result.title} | ${result.reason} | ${result.recommendation} |\n`;
    });
    
    // Clean up the uploaded file
    fs.unlinkSync(filePath);
    
    res.json({ 
      markdownTable: markdownTable,
      results: enhancedResults
    });
    
  } catch (error) {
    console.error('Error processing file:', error);
    
    if (error.response) {
      // The request was made and the server responded with a status code
      // that falls out of the range of 2xx
      return res.status(error.response.status).json({ 
        error: 'Error from external API', 
        details: error.response.data 
      });
    } else if (error.request) {
      // The request was made but no response was received
      return res.status(502).json({ 
        error: 'No response from external API', 
        details: 'The service is currently unavailable' 
      });
    } else {
      // Something happened in setting up the request that triggered an Error
      return res.status(500).json({ 
        error: 'Internal server error', 
        details: error.message 
      });
    }
  }
});

// Simple health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'OK' });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  
  if (err instanceof multer.MulterError) {
    return res.status(400).json({ error: 'File upload error', details: err.message });
  } else if (err.message.includes('Invalid file type')) {
    return res.status(400).json({ error: err.message });
  }
  
  res.status(500).json({ error: 'Internal server error', details: err.message });
});

// Create uploads directory if it doesn't exist
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

// Start the server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});
