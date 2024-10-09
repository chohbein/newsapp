import React from 'react';
import './Header.css';  // Import CSS for styling

function Header() {
  return (
    <header className="header">
      <div className="logo">My Cool Website</div>
      <nav>
        <ul className="nav-links">
          <li><a href="#home">Home</a></li>
          <li><a href="#about">About</a></li>
          <li><a href="#features">Features</a></li>
          <li><a href="#contact">Contact</a></li>
        </ul>
      </nav>
    </header>
  );
}

export default Header;
