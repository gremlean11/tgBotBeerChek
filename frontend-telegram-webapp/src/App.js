import React, { useEffect, useState } from 'react';
import './App.css';

function App() {
  const [tgUser, setTgUser] = useState(null);
  const [beerDb, setBeerDb] = useState([]);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [rating, setRating] = useState(0);
  const [avgRating, setAvgRating] = useState(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      setTgUser(window.Telegram.WebApp.initDataUnsafe.user);
    }
    fetch('/beer_db.json')
      .then(res => res.json())
      .then(data => setBeerDb(data));
  }, []);

  const handleSearch = () => {
    if (!query.trim()) return;
    const q = query.trim().toLowerCase();
    const found = beerDb.find(b => b.name.toLowerCase().includes(q));
    setResult(found || null);
    setMessage(found ? '' : 'Пиво не найдено');
    setRating(0);
    setAvgRating(null);
    if (found) {
      fetch(`https://tgbotbeerchek.onrender.com/rating?beer=${encodeURIComponent(found.name)}`)
        .then(res => res.json())
        .then(data => setAvgRating(data.avg_rating))
        .catch(() => setAvgRating(null));
    }
  };

  const handleRate = (value) => {
    setRating(value);
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.sendData(JSON.stringify({
        action: 'rate',
        beer: result.name,
        rating: value
      }));
      setMessage('Спасибо за вашу оценку!');
    }
    // Отправляем оценку в API для обновления рейтинга
    fetch('https://tgbotbeerchek.onrender.com/rating', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beer: result.name, rating: value })
    }).then(() => handleSearch()); // обновить средний рейтинг
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🍺 Beer Info Mini App</h1>
        {tgUser ? (
          <p>Привет, {tgUser.first_name}!</p>
        ) : (
          <p>Привет, гость!</p>
        )}
        <input
          type="text"
          placeholder="Введите название пива"
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{margin: '10px', padding: '5px'}}
        />
        <button onClick={handleSearch}>Найти</button>
        {result && (
          <div style={{marginTop: 20, background: '#222', padding: 16, borderRadius: 8}}>
            <h2>{result.name}</h2>
            <p><b>Бренд:</b> {result.brand}</p>
            <p><b>Страна:</b> {result.country}</p>
            <p><b>Крепость:</b> {result.abv || '-'}%</p>
            <p><b>Сорт:</b> {result.style || '-'}</p>
            <p><b>Объем:</b> {result.volume || '-'} мл</p>
            <p><b>Упаковка:</b> {result.package || '-'}</p>
            <p><b>Фильтрация:</b> {result.filtration || '-'}</p>
            <p><b>Импорт:</b> {result.imported || '-'}</p>
            <p><b>Вкусовое:</b> {result.flavored || '-'}</p>
            <p><b>Описание:</b> {result.description || '-'}</p>
            <p><b>Рейтинг:</b> {avgRating !== null ? avgRating : (result.rating || '-')}</p>
            <div style={{marginTop: 10}}>
              <span>Ваша оценка: </span>
              {[1,2,3,4,5,6,7,8,9,10].map(i => (
                <button
                  key={i}
                  style={{margin: 2, background: rating === i ? '#4caf50' : '#444', color: '#fff', border: 'none', borderRadius: 4, padding: '2px 6px'}}
                  onClick={() => handleRate(i)}
                >{i}</button>
              ))}
            </div>
          </div>
        )}
        {message && <p style={{color: '#ffb300', marginTop: 20}}>{message}</p>}
      </header>
    </div>
  );
}

export default App;
