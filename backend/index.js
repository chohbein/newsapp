const express = require('express');
const { Pool } = require('pg');
const cors = require('cors');  // Add this line
const app = express();
require('dotenv').config();

// Use CORS
app.use(cors());  // Enable all CORS requests

// Use port 5000 for Express server
const port = process.env.PORT || 5000;
const pool = new Pool({
  user: process.env.DB_USER,
  host: process.env.DB_HOST,
  database: process.env.DB_NAME,
  password: process.env.DB_PASSWORD,
  port: process.env.DB_PORT || 5432,
  ssl: { rejectUnauthorized: false },  // Use SSL for AWS RDS
});


app.get('/api/cards', async (req, res) => {
    const sqlquery = `
      SELECT * 
      FROM similar_articles sa 
      JOIN junct_simart_articles jsa ON jsa.simart_id = sa.simart_id
      JOIN articles a ON a.article_id = jsa.article_id
      WHERE sa.similar_weight >= 0.8
        AND EXISTS (
          SELECT 1
          FROM articles a2 
          JOIN junct_simart_articles jsa2 ON jsa2.article_id = a2.article_id
          WHERE jsa2.simart_id = sa.simart_id
          AND a2.date >= NOW() - INTERVAL '2 days'
        )
      ORDER BY sa.similar_weight DESC;    
    `;
    try {
      const result = await pool.query(sqlquery);
      res.json(result.rows);
    } catch (err) {
      console.error('Error fetching data:', err);
      res.status(500).send('Error fetching data');
    }

});

app.listen(port, () => {
  console.log(`Backend server running on port ${port}`);
});
