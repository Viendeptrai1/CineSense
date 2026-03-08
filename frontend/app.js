/**
 * CineSense catalog frontend with read-only movie details.
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
};

const state = {
    currentPage: 1,
    pageSize: 24,
    totalMovies: 0,
    totalPages: 0,
};

async function getMovies(page = 1, pageSize = 24) {
    const response = await fetch(`${API_BASE_URL}/movies?page=${page}&page_size=${pageSize}`);
    if (!response.ok) {
        throw new Error('Failed to load movies');
    }
    return response.json();
}

async function getMovieDetails(movieId) {
    const response = await fetch(`${API_BASE_URL}/movies/${movieId}`);
    if (!response.ok) {
        throw new Error('Failed to load movie details');
    }
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

function createMovieCard(movie) {
    const card = document.createElement('article');
    card.className = 'card-movie';

    const posterUrl = getPosterUrl(movie.poster_path);
    const genres = (movie.genres || []).slice(0, 2);
    const year = movie.release_date ? new Date(movie.release_date).getFullYear() : 'N/A';

    card.innerHTML = `
        <div class="card-poster">
            ${posterUrl
                ? `<img src="${posterUrl}" alt="${movie.title}" loading="lazy">`
                : '<div style="height:100%;background:#eee;"></div>'}
            ${movie.average_rating ? `<div class="card-star-rating">★ ${movie.average_rating.toFixed(1)}</div>` : ''}
        </div>
        <div class="card-info">
            <h3 class="card-title">${movie.title}</h3>
            <div class="card-meta">
                <span>${year}</span>
                ${genres.map((genre) => `<span class="card-genre">${genre.name}</span>`).join('')}
            </div>
            ${movie.review_count ? `<div class="card-review-count">${movie.review_count} reviews</div>` : ''}
            ${movie.overview ? `<p class="card-overview">${movie.overview.slice(0, 120)}${movie.overview.length > 120 ? '...' : ''}</p>` : ''}
        </div>
    `;

    card.addEventListener('click', () => {
        window.location.href = `movie.html?id=${movie.id}`;
    });

    return card;
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

    if (elements.resultsHeader) {
        elements.resultsHeader.classList.remove('hidden');
        elements.resultsHeader.innerHTML = `
            <h2 class="section-title">Movie Catalog</h2>
            <p style="color: #9ca3af; margin-top: 4px; font-size: 0.95rem;">${data.total} movies in PostgreSQL</p>
        `;
    }

    if (elements.resultsGrid) {
        elements.resultsGrid.innerHTML = '';
        data.movies.forEach((movie) => {
            elements.resultsGrid.appendChild(createMovieCard(movie));
        });
    }

    renderPagination();
}

async function loadMovies() {
    showLoading();
    try {
        const data = await getMovies(state.currentPage, state.pageSize);
        renderMovieList(data);
    } catch (error) {
        console.error('Load movies failed:', error);
        showError(error.message || 'Could not load movie catalog');
    }
}

function renderPagination() {
    removePagination();
    if (!elements.resultsGrid || state.totalPages <= 1) return;

    const container = document.createElement('div');
    container.id = 'paginationControls';
    container.className = 'pagination';

    const pages = generatePageNumbers(state.currentPage, state.totalPages);

    container.innerHTML = `
        <button class="page-btn ${state.currentPage <= 1 ? 'disabled' : ''}" id="prevPage" ${state.currentPage <= 1 ? 'disabled' : ''}>← Prev</button>
        <div class="page-numbers">
            ${pages.map((page) => {
                if (page === '...') return '<span class="page-ellipsis">...</span>';
                return `<button class="page-num ${page === state.currentPage ? 'active' : ''}" data-page="${page}">${page}</button>`;
            }).join('')}
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
    if (total <= 7) {
        return Array.from({ length: total }, (_, index) => index + 1);
    }

    const pages = [1];
    if (current > 3) pages.push('...');

    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let page = start; page <= end; page += 1) {
        pages.push(page);
    }

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
        ? new Date(review.created_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        })
        : 'Unknown date';

    const avatar = review.author_avatar_url
        ? `<img src="${review.author_avatar_url}" class="review-avatar-img" alt="${authorName}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">`
            + `<div class="review-avatar" style="display:none;">${avatarLetter}</div>`
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
                    ${posterUrl
                        ? `<img src="${posterUrl}" alt="${movie.title}" class="detail-poster-image">`
                        : '<div class="detail-poster-placeholder">No poster</div>'}
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

                <section class="reviews-section">
                    <h2 class="detail-section-title">Reviews</h2>
                    ${reviews.length
                        ? `<div class="detail-reviews-list">${reviews.map(createReviewCard).join('')}</div>`
                        : '<div class="loading-container"><p>No reviews available for this movie yet.</p></div>'}
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

function init() {
    if (elements.resultsGrid) {
        loadMovies();
        return;
    }

    loadMovieDetailPage();
}

document.addEventListener('DOMContentLoaded', init);
