/**
 * CineSense - Frontend Application
 * Semantic Movie Search with API Integration
 */

// ============================================
// Configuration
// ============================================
const API_BASE_URL = 'http://localhost:8000';
const TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500';

// ============================================
// DOM Elements
// ============================================
const elements = {
    searchInput: document.getElementById('searchInput'),
    searchBtn: document.getElementById('searchBtn'),
    loading: document.getElementById('loading'),
    error: document.getElementById('error'),
    errorMessage: document.getElementById('errorMessage'),
    resultsHeader: document.getElementById('resultsHeader'),
    queryText: document.getElementById('queryText'),
    resultsCount: document.getElementById('resultsCount'),
    resultsGrid: document.getElementById('resultsGrid'),
    noResults: document.getElementById('noResults'),
    movieModal: document.getElementById('movieModal'),
    closeModal: document.getElementById('closeModal'),
    modalPoster: document.getElementById('modalPoster'),
    modalTitle: document.getElementById('modalTitle'),
    modalYear: document.getElementById('modalYear'),
    modalScore: document.getElementById('modalScore'),
    modalGenres: document.getElementById('modalGenres'),
    modalOverview: document.getElementById('modalOverview'),
    modalReviews: document.getElementById('modalReviews'),
    reviewsList: document.getElementById('reviewsList'),
    hintTags: document.querySelectorAll('.hint-chip'),

    // Auth Elements
    userAuthArea: document.getElementById('userAuthArea'),
    authModal: document.getElementById('authModal'),
    closeAuthModal: document.getElementById('closeAuthModal'),

    // Forms
    loginForm: document.getElementById('loginForm'),
    registerForm: document.getElementById('registerForm'),
    loginUsername: document.getElementById('loginUsername'),
    loginPassword: document.getElementById('loginPassword'),
    submitLogin: document.getElementById('submitLogin'),
    regUsername: document.getElementById('regUsername'),
    regNickname: document.getElementById('regNickname'),
    regPassword: document.getElementById('regPassword'),
    submitRegister: document.getElementById('submitRegister'),
    showRegister: document.getElementById('showRegister'),
    showLogin: document.getElementById('showLogin'),
    loginError: document.getElementById('loginError'),
    regError: document.getElementById('regError'),
};

// ============================================
// State Management
// ============================================
const state = {
    token: localStorage.getItem('token'),
    user: JSON.parse(localStorage.getItem('user') || 'null'),
};

// ============================================
// Auth Functions
// ============================================

async function login(username, password) {
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Sai tên đăng nhập hoặc mật khẩu');

        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        state.token = data.access_token;

        await fetchUserProfile();
        closeAuthModal();
        updateAuthUI();

    } catch (e) {
        elements.loginError.textContent = e.message;
        elements.loginError.style.display = 'block';
    }
}

async function register(username, nickname, password) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, nickname, password })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Đăng ký thất bại');
        }

        // Auto login after register
        await login(username, password);

    } catch (e) {
        elements.regError.textContent = e.message;
        elements.regError.style.display = 'block';
    }
}

async function fetchUserProfile() {
    if (!state.token) return;

    const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { 'Authorization': `Bearer ${state.token}` }
    });

    if (response.ok) {
        const user = await response.json();
        localStorage.setItem('user', JSON.stringify(user));
        state.user = user;
    } else {
        logout(); // Token invalid
    }
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    state.token = null;
    state.user = null;
    updateAuthUI();
    window.location.reload();
}

function updateAuthUI() {
    if (state.user) {
        // Render User Widget
        elements.userAuthArea.innerHTML = `
            <div class="user-widget" id="userWidget" title="Click to logout">
                <div class="nav-item">${state.user.nickname}</div>
                <div class="avatar">${state.user.nickname.charAt(0).toUpperCase()}</div>
            </div>
        `;
        // Add Logout Listener
        document.getElementById('userWidget').addEventListener('click', () => {
            if (confirm('Bạn có muốn đăng xuất?')) logout();
        });
    } else {
        // Render Login Button
        elements.userAuthArea.innerHTML = `<button class="btn-primary" id="btnLogin">Đăng nhập</button>`;
        // Add Login Listener
        document.getElementById('btnLogin').addEventListener('click', openAuthModal);
    }
    updatePersonalizedHints();
}

function updatePersonalizedHints() {
    const hintContainer = document.querySelector('.hero-hints');
    if (!hintContainer) return;

    if (state.user) {
        // Personalize based on user name or random for now
        hintContainer.innerHTML = `
            <span class="hint-chip" data-query="Phim tâm lý tội phạm gay cấn">🕵️ Tội phạm</span>
            <span class="hint-chip" data-query="Phim hoạt hình Ghibli">anime ghibli</span>
            <span class="hint-chip" data-query="Phim khoa học viễn tưởng không gian">🚀 Sci-Fi</span>
        `;
    } else {
        // Default hints
        hintContainer.innerHTML = `
            <span class="hint-chip" data-query="Phim hại não plot twist">🤯 Hại não</span>
            <span class="hint-chip" data-query="Phim tình cảm lãng mạn nhẹ nhàng">💕 Lãng mạn</span>
            <span class="hint-chip" data-query="Phim hành động kịch tính đua xe">🏎️ Hành động</span>
        `;
    }

    // Re-attach listeners
    document.querySelectorAll('.hint-chip').forEach(tag => {
        tag.addEventListener('click', () => {
            if (elements.searchInput) {
                elements.searchInput.value = tag.dataset.query;
                handleSearch();
            }
        });
    });
}

function openAuthModal() {
    elements.authModal.classList.remove('hidden');
    elements.loginForm.classList.remove('hidden');
    elements.registerForm.classList.add('hidden');
}

function closeAuthModal() {
    elements.authModal.classList.add('hidden');
    elements.loginUsername.value = '';
    elements.loginPassword.value = '';
    elements.loginError.style.display = 'none';
}

// ============================================
// API Functions
// ============================================

/**
 * Semantic search for movies
 */
async function searchMovies(query, limit = 12) {
    const response = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Search failed');
    }

    return response.json();
}

/**
 * Get recent/trending movies
 */
async function getRecentMovies(limit = 24) {
    const response = await fetch(`${API_BASE_URL}/movies?limit=${limit}`);

    if (!response.ok) {
        throw new Error('Failed to load recent movies');
    }

    return response.json();
}

/**
 * Get movie details with reviews
 */
async function getMovieDetails(movieId) {
    const response = await fetch(`${API_BASE_URL}/movies/${movieId}`);

    if (!response.ok) {
        throw new Error('Failed to load movie details');
    }

    return response.json();
}

/**
 * Get API health/stats
 */
async function getHealthStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            return response.json();
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
    return null;
}

// ============================================
// UI Functions & Routing Logic
// ============================================

const isMoviePage = window.location.pathname.includes('movie.html');

function showLoading() {
    if (elements.loading) elements.loading.classList.remove('hidden');
    // Hide home page elements if they exist
    if (elements.error) elements.error.classList.add('hidden');
    if (elements.resultsHeader) elements.resultsHeader.classList.add('hidden');
    if (elements.resultsGrid) elements.resultsGrid.innerHTML = '';
    if (elements.noResults) elements.noResults.classList.add('hidden');
}

function hideLoading() {
    if (elements.loading) elements.loading.classList.add('hidden');
}

function showError(message) {
    elements.error.classList.remove('hidden');
    elements.errorMessage.textContent = message;
}

function showNoResults() {
    elements.loading.classList.add('hidden');
    elements.noResults.classList.remove('hidden');
}

function getScoreClass(score) {
    if (score >= 0.7) return 'high';
    if (score >= 0.5) return 'medium';
    return 'low';
}

function getPosterUrl(posterPath) {
    if (!posterPath) return null;
    return `${TMDB_IMAGE_BASE}${posterPath}`;
}

/**
 * Render a movie card
 */
function createMovieCard(movie) {
    const card = document.createElement('div');
    card.className = 'card-movie';
    card.dataset.movieId = movie.movie_id;

    const posterUrl = getPosterUrl(movie.poster_path);
    const genres = (movie.genres || []).slice(0, 2);

    card.innerHTML = `
        <div class="card-poster">
            ${posterUrl
            ? `<img src="${posterUrl}" alt="${movie.title}" loading="lazy">`
            : '<div style="height:100%;background:#eee;"></div>'
        }
            <div class="card-rating">${movie.score ? Math.round(movie.score * 100) : 'N/A'}%</div>
        </div>
        <div class="card-info">
            <h3 class="card-title">${movie.title}</h3>
            <div class="card-meta">
                <span>${movie.year || 'N/A'}</span>
                ${genres.map(g => `<span class="card-genre">${g}</span>`).join('')}
            </div>
        </div>
    `;

    // Navigate to new page instead of modal
    card.addEventListener('click', () => {
        window.location.href = `movie.html?id=${movie.movie_id}`;
    });

    return card;
}

/**
 * Render search results
 */
function renderResults(data) {
    hideLoading();

    if (!data.results || data.results.length === 0) {
        showNoResults();
        return;
    }

    elements.resultsHeader.classList.remove('hidden');
    elements.queryText.textContent = data.query;
    elements.resultsCount.textContent = `${data.total_results} phim được tìm thấy`;

    elements.resultsGrid.innerHTML = '';
    data.results.forEach(movie => {
        elements.resultsGrid.appendChild(createMovieCard(movie));
    });
}

/**
 * Render Movie Detail Page
 */
async function renderMoviePage(movieId) {
    const container = document.getElementById('movieDetailContainer');
    if (!container) return;

    try {
        const movie = await getMovieDetails(movieId);
        const posterUrl = getPosterUrl(movie.poster_path);

        // Populate page content
        container.innerHTML = `
            <div class="movie-detail-layout" style="display: flex; gap: 40px; align-items: flex-start;">
                <div class="detail-poster" style="flex: 0 0 300px;">
                    <img src="${posterUrl}" alt="${movie.title}" style="width: 100%; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                </div>
                <div class="detail-info" style="flex: 1;">
                    <h1 style="font-size: 2.5rem; margin-bottom: 12px;">${movie.title}</h1>
                    <div class="meta-badges" style="display: flex; gap: 12px; margin-bottom: 24px; font-size: 0.9rem; color: #aaa;">
                        <span>${movie.release_date ? new Date(movie.release_date).getFullYear() : 'N/A'}</span>
                        <span>•</span>
                        <span>${movie.genres.map(g => g.name).join(', ')}</span>
                        ${movie.score ? `<span>•</span><span style="color: #46d369; font-weight: bold;">${Math.round(movie.score * 100)}% Match</span>` : ''}
                    </div>
                    
                    <p class="overview" style="font-size: 1.1rem; line-height: 1.6; color: #ddd; margin-bottom: 40px;">
                        ${movie.overview || 'Chưa có tóm tắt cho phim này.'}
                    </p>

                    <div class="reviews-section">
                        <h3 style="margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px;">Đánh giá & Bình luận</h3>
                        <div id="reviewsList" style="display: flex; flex-direction: column; gap: 16px;"></div>
                    </div>
                </div>
            </div>
        `;

        // We need to re-bind the element because we just overwrote innerHTML
        elements.reviewsList = document.getElementById('reviewsList');
        renderReviews(movie);

    } catch (error) {
        container.innerHTML = `<div class="error-state"><h2>Oops!</h2><p>${error.message}</p><a href="index.html" class="btn-primary">Quay lại trang chủ</a></div>`;
    }
}

// Deprecated: Modal function replaced by page
function openMovieModal(movieId) {
    window.location.href = `movie.html?id=${movieId}`;
}

function renderReviews(movie) {
    const reviews = movie.reviews || [];

    if (reviews.length === 0) {
        elements.reviewsList.innerHTML = '<p class="no-reviews">Chưa có đánh giá nào. Hãy là người đầu tiên!</p>';
    } else {
        elements.reviewsList.innerHTML = reviews.map(review => {
            // Prioritize author_name -> user -> source
            let authorName = review.author_name || review.user || review.source;
            if (authorName === 'tmdb') authorName = 'TMDB Reviewer';

            // Avatar logic: Image -> Letter
            let avatarHtml;
            if (review.author_avatar_url) {
                avatarHtml = `<img src="${review.author_avatar_url}" class="review-avatar-img" alt="${authorName}" onerror="this.style.display='none'">`;
            } else {
                const avatarLetter = authorName.charAt(0).toUpperCase();
                const colors = ['#e50914', '#b20710', '#141414', '#46d369', '#333'];
                const randomColor = colors[Math.floor(Math.random() * colors.length)];
                avatarHtml = `<div class="review-avatar" style="background: ${randomColor}">${avatarLetter}</div>`;
            }

            // Simple Markdown Parser
            const parseMarkdown = (text) => {
                if (!text) return '';
                return text
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                    .replace(/\n/g, '<br>');
            };

            return `
            <div class="review-card">
                ${avatarHtml}
                <div class="review-body">
                    <div class="review-header">
                        <span class="review-author">${authorName}</span>
                        ${review.rating ? `<span class="review-rating">★ ${review.rating}</span>` : ''}
                    </div>
                    <div class="review-meta">
                        <span>${new Date(review.created_at).toLocaleDateString('vi-VN')}</span>
                        <span>•</span>
                        <span>${review.source === 'tmdb' ? 'Verified Source' : 'Thành viên CineSense'}</span>
                    </div>
                    <p class="review-content">${parseMarkdown(review.content)}</p>
                    <div class="review-footer">
                        <button class="btn-like-sm ${review.is_liked ? 'liked' : ''}">
                            ❤️ ${review.likes_count || 0} Hữu ích
                        </button>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }



    // Show "Write Review" if logged in
    if (state.user) {
        const formHtml = `
            <div class="write-review">
                <h3>Viết đánh giá của bạn</h3>
                <textarea id="reviewContent" placeholder="Bạn nghĩ gì về phim này?"></textarea>
                <div class="review-actions">
                    <input type="number" id="reviewRating" min="1" max="10" step="0.5" placeholder="Điểm (1-10)">
                    <button id="submitReviewBtn" class="btn-primary" onclick="postReview('${movie.id}')">Gửi đánh giá</button>
                </div>
            </div>
        `;
        // Prepend to list
        if (elements.reviewsList) elements.reviewsList.insertAdjacentHTML('afterbegin', formHtml);
    } else {
        if (elements.reviewsList) {
            elements.reviewsList.insertAdjacentHTML('afterbegin',
                '<p class="login-prompt">👉 <a href="#" onclick="closeMovieModal(); openAuthModal();">Đăng nhập</a> để viết đánh giá.</p>'
            );
        }
    }

    if (elements.modalReviews) elements.modalReviews.classList.remove('hidden');
}

async function postReview(movieId) {
    const content = document.getElementById('reviewContent').value;
    const rating = document.getElementById('reviewRating').value;

    if (!content) return alert('Vui lòng nhập nội dung!');

    try {
        const response = await fetch(`${API_BASE_URL}/movies/${movieId}/reviews`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify({ content, rating: parseFloat(rating) })
        });

        if (response.ok) {
            alert('Đánh giá thành công!');
            openMovieModal(movieId); // Reload
        } else {
            alert('Lỗi khi gửi đánh giá');
        }
    } catch (e) {
        console.error(e);
    }
}



function closeMovieModal() {
    if (elements.movieModal) elements.movieModal.classList.add('hidden');
    document.body.style.overflow = '';
}

// ============================================
// Event Handlers
// ============================================

async function handleSearch() {
    const query = elements.searchInput.value.trim();

    if (!query) {
        elements.searchInput.focus();
        return;
    }

    showLoading();

    try {
        const results = await searchMovies(query);
        renderResults(results);
    } catch (error) {
        hideLoading();
        showError(error.message);
        console.error('Search error:', error);
    }
}

// ============================================
// Initialize
// ============================================

// ============================================
// Initialize
// ============================================

function init() {
    // Common Auth Events (Header)
    updateAuthUI();
    if (state.token) fetchUserProfile();

    if (elements.closeAuthModal) elements.closeAuthModal.addEventListener('click', closeAuthModal);
    if (elements.showRegister) elements.showRegister.addEventListener('click', (e) => {
        e.preventDefault();
        elements.loginForm.classList.add('hidden');
        elements.registerForm.classList.remove('hidden');
    });
    if (elements.showLogin) elements.showLogin.addEventListener('click', (e) => {
        e.preventDefault();
        elements.registerForm.classList.add('hidden');
        elements.loginForm.classList.remove('hidden');
    });
    if (elements.submitLogin) elements.submitLogin.addEventListener('click', () => {
        login(elements.loginUsername.value, elements.loginPassword.value);
    });
    if (elements.submitRegister) elements.submitRegister.addEventListener('click', () => {
        register(elements.regUsername.value, elements.regNickname.value, elements.regPassword.value);
    });

    // PAGE SPECIFIC LOGIC
    if (isMoviePage) {
        // --- Movie Detail Page Logic ---
        const urlParams = new URLSearchParams(window.location.search);
        const movieId = urlParams.get('id');
        if (movieId) {
            renderMoviePage(movieId);
        } else {
            document.getElementById('movieDetailContainer').innerHTML = '<p>Không tìm thấy ID phim.</p>';
        }

    } else {
        // --- Home Page Logic ---
        if (elements.searchBtn) elements.searchBtn.addEventListener('click', handleSearch);
        if (elements.searchInput) elements.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSearch();
        });

        // Hint tags
        elements.hintTags.forEach(tag => {
            tag.addEventListener('click', () => {
                if (elements.searchInput) {
                    elements.searchInput.value = tag.dataset.query;
                    handleSearch();
                }
            });
        });

        // Initial Data Load
        loadInitialMovies();
    }
}

async function loadInitialMovies() {
    try {
        const data = await getRecentMovies();
        hideLoading();

        if (data.results && data.results.length > 0) {
            elements.resultsHeader.classList.remove('hidden');
            elements.resultsHeader.innerHTML = '<h2 class="section-title">✨ Phim mới cập nhật</h2>';

            elements.resultsGrid.innerHTML = '';
            data.results.forEach(movie => {
                elements.resultsGrid.appendChild(createMovieCard(movie));
            });
        } else {
            showNoResults();
        }
    } catch (e) {
        hideLoading();
        console.error('Initial load failed:', e);
    }
}

// End of file

// Start app
document.addEventListener('DOMContentLoaded', init);
