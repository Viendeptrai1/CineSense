/**
 * CineSense catalog frontend with movie details and recommendations.
 */

const API_BASE_URL = 'http://localhost:8000';
const TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500';

const elements = {
    resultsHeader: document.getElementById('resultsHeader'),
    resultsGrid: document.getElementById('resultsGrid'),
    loading: document.getElementById('loading'),
    noResults: document.getElementById('noResults'),
    error: document.getElementById('error'),
    errorMessage: document.getElementById('errorMessage'),
    movieDetailContainer: document.getElementById('movieDetailContainer'),
    recommendationQuery: document.getElementById('recommendationQuery'),
    recommendationSearchBtn: document.getElementById('recommendationSearchBtn'),
    recommendationResetBtn: document.getElementById('recommendationResetBtn'),
};

const state = {
    currentPage: 1,
    pageSize: 24,
    totalMovies: 0,
    totalPages: 0,
    mode: 'catalog',
};

async function getMovies(page = 1, pageSize = 24) {
    const response = await fetch(`${API_BASE_URL}/movies?page=${page}&page_size=${pageSize}`);
    if (!response.ok) throw new Error('Failed to load movies');
    return response.json();
}

async function getMovieDetails(movieId) {
    const response = await fetch(`${API_BASE_URL}/movies/${movieId}`);
    if (!response.ok) throw new Error('Failed to load movie details');
    return response.json();
}

async function getSimilarMovies(movieId, limit = 8) {
    const response = await fetch(`${API_BASE_URL}/movies/${movieId}/similar?limit=${limit}`);
    if (!response.ok) throw new Error('Similar movies are unavailable');
    return response.json();
}

async function getTrendingRecommendations(limit = 24) {
    const response = await fetch(`${API_BASE_URL}/recommendations/trending?limit=${limit}`);
    if (!response.ok) throw new Error('Recommendations are unavailable');
    return response.json();
}

async function searchRecommendations(query, limit = 24) {
    const response = await fetch(`${API_BASE_URL}/recommendations/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit }),
    });
    if (!response.ok) throw new Error('Search recommendations are unavailable');
    return response.json();
}

async function getAbsaAnalysis(movieId) {
    const response = await fetch(`${API_BASE_URL}/absa/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie_id: movieId }),
    });
    if (response.status === 503) return null;
    if (!response.ok) throw new Error('ABSA unavailable');
    return response.json();
}

function showLoading() {
    if (elements.loading) elements.loading.classList.remove('hidden');
    if (elements.error) elements.error.classList.add('hidden');
    if (elements.noResults) elements.noResults.classList.add('hidden');
    if (elements.resultsHeader) elements.resultsHeader.classList.add('hidden');
}

function hideLoading() {
    if (elements.loading) elements.loading.classList.add('hidden');
}

function showError(message) {
    hideLoading();
    if (elements.error) elements.error.classList.remove('hidden');
    if (elements.errorMessage) elements.errorMessage.textContent = message;
}

function showNoResults() {
    hideLoading();
    if (elements.noResults) elements.noResults.classList.remove('hidden');
}

function getPosterUrl(posterPath) {
    return posterPath ? `${TMDB_IMAGE_BASE}${posterPath}` : null;
}

function normalizeMovieData(movie) {
    const normalizedGenres = (movie.genres || []).map((genre) =>
        typeof genre === 'string' ? { name: genre } : genre
    );
    return {
        id: movie.id || movie.movie_id,
        title: movie.title,
        overview: movie.overview,
        poster_path: movie.poster_path,
        review_count: movie.review_count || 0,
        average_rating: movie.average_rating ?? null,
        release_date: movie.release_date || null,
        genres: normalizedGenres,
        score: movie.score ?? null,
    };
}

function createMovieCard(inputMovie) {
    const movie = normalizeMovieData(inputMovie);
    const card = document.createElement('article');
    card.className = 'card-movie';

    const posterUrl = getPosterUrl(movie.poster_path);
    const genres = (movie.genres || []).slice(0, 2);
    const year = movie.release_date ? new Date(movie.release_date).getFullYear() : 'N/A';

    card.innerHTML = `
        <div class="card-poster">
            ${posterUrl ? `<img src="${posterUrl}" alt="${movie.title}" loading="lazy">` : '<div style="height:100%;background:#eee;"></div>'}
            ${movie.review_count ? '<div class="card-review-badge">Has reviews</div>' : ''}
            ${movie.average_rating ? `<div class="card-star-rating">★ ${movie.average_rating.toFixed(1)}</div>` : ''}
        </div>
        <div class="card-info">
            <h3 class="card-title">${movie.title}</h3>
            <div class="card-meta">
                <span>${year}</span>
                ${genres.map((genre) => `<span class="card-genre">${genre.name}</span>`).join('')}
            </div>
            ${movie.review_count ? `<div class="card-review-count">${movie.review_count} reviews</div>` : ''}
            ${movie.score !== null && movie.score !== undefined ? `<div class="card-review-count">Similarity: ${movie.score.toFixed(2)}</div>` : ''}
            ${movie.overview ? `<p class="card-overview">${movie.overview.slice(0, 120)}${movie.overview.length > 120 ? '...' : ''}</p>` : ''}
        </div>
    `;

    card.addEventListener('click', () => {
        window.location.href = `movie.html?id=${movie.id}`;
    });

    return card;
}

function renderMovieCards(movies) {
    if (!elements.resultsGrid) return;
    elements.resultsGrid.innerHTML = '';
    movies.forEach((movie) => {
        elements.resultsGrid.appendChild(createMovieCard(movie));
    });
}

function renderHeader(title, subtitle) {
    if (!elements.resultsHeader) return;
    elements.resultsHeader.classList.remove('hidden');
    elements.resultsHeader.innerHTML = `
        <h2 class="section-title">${title}</h2>
        <p style="color: #9ca3af; margin-top: 4px; font-size: 0.95rem;">${subtitle}</p>
    `;
}

function renderMovieList(data) {
    hideLoading();
    if (!data.movies || data.movies.length === 0) {
        removePagination();
        showNoResults();
        return;
    }

    state.totalMovies = data.total;
    state.totalPages = Math.ceil(data.total / data.page_size);
    state.currentPage = data.page;

    renderHeader('Movie Catalog', `${data.total} movies in PostgreSQL`);
    renderMovieCards(data.movies);
    renderPagination();
}

async function loadMovies() {
    state.mode = 'catalog';
    showLoading();
    try {
        const data = await getMovies(state.currentPage, state.pageSize);
        renderMovieList(data);
    } catch (error) {
        console.error('Load movies failed:', error);
        showError(error.message || 'Could not load movie catalog');
    }
}

async function loadTrendingRecommendations() {
    state.mode = 'recommendation';
    showLoading();
    removePagination();
    try {
        const data = await getTrendingRecommendations(24);
        hideLoading();
        if (!data.results.length) return showNoResults();
        renderHeader('Top Reviewed Picks', `Model: ${data.model}`);
        renderMovieCards(data.results);
    } catch (error) {
        // Fallback gracefully to catalog when artifacts are missing.
        console.warn('Trending recommendations unavailable:', error.message);
        loadMovies();
    }
}

async function runRecommendationSearch() {
    if (!elements.recommendationQuery) return;
    const query = elements.recommendationQuery.value.trim();
    if (!query) {
        loadMovies();
        return;
    }

    state.mode = 'recommendation';
    showLoading();
    removePagination();
    try {
        const data = await searchRecommendations(query, 24);
        hideLoading();
        if (!data.results.length) return showNoResults();
        renderHeader('Recommendation Search', `"${query}" • model: ${data.model}`);
        renderMovieCards(data.results);
    } catch (error) {
        console.error('Recommendation search failed:', error);
        showError(error.message || 'Recommendation search is unavailable');
    }
}

function renderPagination() {
    removePagination();
    if (!elements.resultsGrid || state.totalPages <= 1 || state.mode !== 'catalog') return;

    const container = document.createElement('div');
    container.id = 'paginationControls';
    container.className = 'pagination';
    const pages = generatePageNumbers(state.currentPage, state.totalPages);

    container.innerHTML = `
        <button class="page-btn ${state.currentPage <= 1 ? 'disabled' : ''}" id="prevPage" ${state.currentPage <= 1 ? 'disabled' : ''}>← Prev</button>
        <div class="page-numbers">
            ${pages.map((page) => page === '...' ? '<span class="page-ellipsis">...</span>' : `<button class="page-num ${page === state.currentPage ? 'active' : ''}" data-page="${page}">${page}</button>`).join('')}
        </div>
        <button class="page-btn ${state.currentPage >= state.totalPages ? 'disabled' : ''}" id="nextPage" ${state.currentPage >= state.totalPages ? 'disabled' : ''}>Next →</button>
    `;

    elements.resultsGrid.parentNode.insertBefore(container, elements.resultsGrid.nextSibling);
    document.getElementById('prevPage').addEventListener('click', () => {
        if (state.currentPage <= 1) return;
        state.currentPage -= 1;
        loadMovies();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    document.getElementById('nextPage').addEventListener('click', () => {
        if (state.currentPage >= state.totalPages) return;
        state.currentPage += 1;
        loadMovies();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    container.querySelectorAll('.page-num').forEach((button) => {
        button.addEventListener('click', () => {
            const page = Number.parseInt(button.dataset.page, 10);
            if (page === state.currentPage) return;
            state.currentPage = page;
            loadMovies();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
}

function generatePageNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);
    const pages = [1];
    if (current > 3) pages.push('...');
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let page = start; page <= end; page += 1) pages.push(page);
    if (current < total - 2) pages.push('...');
    pages.push(total);
    return pages;
}

function removePagination() {
    const existing = document.getElementById('paginationControls');
    if (existing) existing.remove();
}

function createReviewCard(review) {
    const authorName = review.author_name || review.source || 'Unknown reviewer';
    const avatarLetter = authorName.charAt(0).toUpperCase();
    const date = review.created_at
        ? new Date(review.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
        : 'Unknown date';

    const avatar = review.author_avatar_url
        ? `<img src="${review.author_avatar_url}" class="review-avatar-img" alt="${authorName}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="review-avatar" style="display:none;">${avatarLetter}</div>`
        : `<div class="review-avatar">${avatarLetter}</div>`;

    return `
        <article class="review-card">
            ${avatar}
            <div class="review-body">
                <div class="review-header">
                    <span class="review-author">${authorName}</span>
                    ${review.rating !== null && review.rating !== undefined ? `<span class="review-rating">★ ${review.rating}</span>` : ''}
                </div>
                <div class="review-meta">
                    <span>${date}</span>
                    <span>•</span>
                    <span>${review.source.toUpperCase()}</span>
                </div>
                <p class="review-content">${review.content}</p>
            </div>
        </article>
    `;
}

function renderSimilarList(rows) {
    const container = document.getElementById('detailSimilarList');
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = '<p style="color:#666;">No similar recommendations yet.</p>';
        return;
    }
    container.innerHTML = rows.map((item) => `
        <a class="similar-item" href="movie.html?id=${item.movie_id}">
            <span class="similar-title">${item.title}</span>
            ${item.score !== null && item.score !== undefined ? `<span class="similar-score">${item.score.toFixed(2)}</span>` : ''}
        </a>
    `).join('');
}

function sentimentIcon(sentiment) {
    if (sentiment === 'positive') return '+';
    if (sentiment === 'negative') return '−';
    return '0';
}

function renderAbsaSection(data) {
    const container = document.getElementById('detailAbsaList');
    if (!container) return;
    if (!data || !data.aspects || !data.aspects.length) {
        container.innerHTML = '<p style="color:#666;">Aspect sentiment not available. Train ABSA model to enable.</p>';
        return;
    }
    container.innerHTML = `
        <div class="absa-grid">
            ${data.aspects.map((a) => `
                <div class="absa-item">
                    <span class="absa-aspect">${a.aspect}</span>
                    <span class="absa-sentiment" data-sentiment="${a.sentiment}">${sentimentIcon(a.sentiment)} ${a.sentiment}</span>
                    <span class="absa-score">${(a.score * 100).toFixed(0)}%</span>
                </div>
            `).join('')}
        </div>
    `;
}

function renderMoviePage(movie) {
    if (!elements.movieDetailContainer) return;
    const posterUrl = getPosterUrl(movie.poster_path);
    const year = movie.release_date ? new Date(movie.release_date).getFullYear() : 'N/A';
    const genres = (movie.genres || []).map((genre) => genre.name).join(', ') || 'Unknown';
    const reviews = movie.reviews || [];

    elements.movieDetailContainer.innerHTML = `
        <div class="movie-detail-layout">
            <div class="detail-poster-column">
                <div class="detail-poster-card">
                    ${posterUrl ? `<img src="${posterUrl}" alt="${movie.title}" class="detail-poster-image">` : '<div class="detail-poster-placeholder">No poster</div>'}
                </div>
                <a href="index.html" class="btn-primary detail-back-link">Back to catalog</a>
            </div>
            <div class="detail-content-column">
                <div class="detail-hero">
                    <h1 class="detail-title">${movie.title}</h1>
                    <div class="detail-meta">
                        <span>${year}</span>
                        <span>•</span>
                        <span>${genres}</span>
                        <span>•</span>
                        <span>${movie.review_count} reviews</span>
                        ${movie.average_rating !== null && movie.average_rating !== undefined ? `<span>•</span><span>★ ${movie.average_rating.toFixed(1)}</span>` : ''}
                    </div>
                    <p class="detail-overview">${movie.overview || 'No overview available for this movie yet.'}</p>
                </div>
                <section class="similar-section">
                    <h2 class="detail-section-title">Similar Movies</h2>
                    <p class="detail-hint">
                        When you open this page, the app calls <code>/movies/${movie.id}/similar</code>,
                        which reads precomputed neighbors from TF-IDF / Sentence-BERT artifacts.
                    </p>
                    <div id="detailSimilarList" class="similar-list">
                        <p style="color:#666;">Loading recommendations...</p>
                    </div>
                </section>
                <section class="absa-section">
                    <h2 class="detail-section-title">Aspect-Based Sentiment</h2>
                    <p class="detail-hint">
                        Sentiment by aspect (script, acting, visuals, etc.) powered by the ABSA model behind
                        <code>/absa/analyze</code>. Each tile below comes from processing the movie's English reviews.
                    </p>
                    <div id="detailAbsaList" class="absa-list">
                        <p style="color:#666;">Loading...</p>
                    </div>
                </section>
                <section class="reviews-section">
                    <h2 class="detail-section-title">Reviews</h2>
                    ${reviews.length ? `<div class="detail-reviews-list">${reviews.map(createReviewCard).join('')}</div>` : '<div class="loading-container"><p>No reviews available for this movie yet.</p></div>'}
                </section>
            </div>
        </div>
    `;
}

async function loadMovieDetailPage() {
    if (!elements.movieDetailContainer) return;
    const params = new URLSearchParams(window.location.search);
    const movieId = params.get('id');
    if (!movieId) {
        elements.movieDetailContainer.innerHTML = `
            <div class="loading-container">
                <h2>Movie not found</h2>
                <p>Missing movie id in URL.</p>
                <p><a href="index.html" class="btn-primary">Back to catalog</a></p>
            </div>
        `;
        return;
    }

    try {
        const movie = await getMovieDetails(movieId);
        renderMoviePage(movie);
        try {
            const similar = await getSimilarMovies(movie.id, 8);
            renderSimilarList(similar.results || []);
        } catch (_error) {
            renderSimilarList([]);
        }
        try {
            const absa = await getAbsaAnalysis(movie.id);
            renderAbsaSection(absa);
        } catch (_err) {
            renderAbsaSection(null);
        }
    } catch (error) {
        console.error('Load movie detail failed:', error);
        elements.movieDetailContainer.innerHTML = `
            <div class="loading-container">
                <h2>Could not load movie</h2>
                <p>${error.message || 'Please try again later.'}</p>
                <p><a href="index.html" class="btn-primary">Back to catalog</a></p>
            </div>
        `;
    }
}

function setupCatalogInteractions() {
    if (elements.recommendationSearchBtn) {
        elements.recommendationSearchBtn.addEventListener('click', () => runRecommendationSearch());
    }
    if (elements.recommendationQuery) {
        elements.recommendationQuery.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') runRecommendationSearch();
        });
    }
    if (elements.recommendationResetBtn) {
        elements.recommendationResetBtn.addEventListener('click', () => {
            if (elements.recommendationQuery) elements.recommendationQuery.value = '';
            state.currentPage = 1;
            loadMovies();
        });
    }
}

function init() {
    if (elements.resultsGrid) {
        setupCatalogInteractions();
        loadTrendingRecommendations();
        return;
    }
    loadMovieDetailPage();
}

document.addEventListener('DOMContentLoaded', init);
