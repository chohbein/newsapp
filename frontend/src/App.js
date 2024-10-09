import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [groupedArticles, setGroupedArticles] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedGroup, setSelectedGroup] = useState(null); // State to manage selected group for modal
  const [isModalOpen, setIsModalOpen] = useState(false); // State to control modal visibility

  useEffect(() => {
    axios.get('http://localhost:5000/api/cards')
      .then(response => {
        console.log('Fetched articles:', response.data);
        const grouped = response.data.reduce((acc, article) => {
          const simartId = article.simart_id;
          if (!acc[simartId]) {
            acc[simartId] = [];
          }
          acc[simartId].push(article);
          return acc;
        }, {});

        setGroupedArticles(grouped);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error fetching articles:', error);
        setLoading(false);
      });
  }, []);

  const findShortestArticleWithImage = (articles) => {
    if (!articles || articles.length === 0) return null;
  
    // Filter articles that have a valid image (not "NaN", undefined, null, or empty)
    const articlesWithImage = articles.filter(article => {
      const isStringNan = article.image === "NaN";
      const hasValidImage = (
        article.image && 
        typeof article.image === 'string' &&
        article.image.trim() !== '' &&
        !isStringNan
      );
  
      if (!hasValidImage) {
        console.log(`Invalid image for article: "${article.title}", Image URL: ${article.image}`);
      }
  
      return hasValidImage;
    });
  
    // If there are articles with images, find the shortest title among them
    if (articlesWithImage.length > 0) {
      return articlesWithImage.reduce((shortest, current) => 
        current.title.length < shortest.title.length ? current : shortest
      );
    }
  
    // If no articles with images, fallback to the shortest article regardless of image
    return articles.reduce((shortest, current) => 
      current.title.length < shortest.title.length ? current : shortest
    );
  };
  
  // Helper function to format the date
  const formatDate = (dateString) => {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
  };

  const openModal = (group) => {
    setSelectedGroup(group); // Set the selected group for modal display
    setIsModalOpen(true);    // Open the modal
  };

  const closeModal = () => {
    setIsModalOpen(false);   // Close the modal
    setSelectedGroup(null);  // Clear the selected group
  };

  // Closes modal if clicking outside of the modal content
  const handleClickOutside = (e) => {
    if (e.target.className === 'modal-overlay') {
      closeModal();
    }
  };

  if (loading) {
    return <div>Loading articles...</div>;
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="logo">NewsSh!t</div>
          <nav>
            <ul className="nav-links">
              <li><a href="#search">Search Articles</a></li>
              <li><a href="#about">About</a></li>
            </ul>
          </nav>
        </div>
      </header>

      <main className="main-content">
        {Object.keys(groupedArticles).length > 0 ? (
          Object.keys(groupedArticles).map(simartId => {
            const shortestArticle = findShortestArticleWithImage(groupedArticles[simartId]);
            return (
              <div 
                key={simartId} 
                className="card" 
                onClick={() => openModal(groupedArticles[simartId])} // Open modal on card click
                style={{ cursor: 'pointer' }} // Change cursor to pointer
              >
                {shortestArticle && (
                  <>
                    <h2>{shortestArticle.title}</h2>
                    <p>{formatDate(shortestArticle.date)}</p>
                    <img src={shortestArticle.image} alt='' className="article-image" />
                  </>
                )}
                <p>As Covered By:</p>
                <ul>
                  {groupedArticles[simartId].map(article => (
                    <li key={article.article_id}>
                      <p><a href={article.url} target="_blank" rel="noopener noreferrer" style={{color:'lightblue'}}>{article.article_source}</a></p>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })
        ) : (
          <p>No articles found</p>
        )}
      </main>

      {isModalOpen && selectedGroup && (
        <Modal onClose={closeModal} articles={selectedGroup} handleClickOutside={handleClickOutside} />
      )}
    </div>
  );
}

function Modal({ onClose, articles, handleClickOutside }) {

  // Helper function to format the date
  const formatDate = (dateString) => {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
  };

  return (
    <div className="modal-overlay" onClick={handleClickOutside}>
      <div className="modal-content" onClick={(e) => e.stopPropagation() /* Prevent closing when clicking inside */}>
        <button className="modal-close" onClick={onClose}>X</button>
        <ul>
          {articles.map(article => (
            <li key={article.article_id}>
              <p style={{color:'white'}}><strong>{article.title}</strong></p>
              <p><a href={article.url} target="_blank" rel="noopener noreferrer" style={{color:'lightblue'}}>{article.article_source}</a></p>
              {/* Format the date */}
              <p style={{color:'white'}}><strong>{formatDate(article.date)}</strong></p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default App;
