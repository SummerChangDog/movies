// DOM元素
const movieInput = document.getElementById('movieInput');
const searchBtn = document.getElementById('searchBtn');
const loader = document.getElementById('loader');
const error = document.getElementById('error');
const errorText = document.getElementById('errorText');
const results = document.getElementById('results');

// 电影信息元素
const moviePoster = document.getElementById('moviePoster');
const movieTitle = document.getElementById('movieTitle');
const movieYear = document.getElementById('movieYear');
const movieGenre = document.getElementById('movieGenre');
const movieDirector = document.getElementById('movieDirector');
const movieActors = document.getElementById('movieActors');
const moviePlot = document.getElementById('moviePlot');

// 评分元素
const doubanScore = document.getElementById('doubanScore');
const doubanVotes = document.getElementById('doubanVotes');
const doubanStars = document.getElementById('doubanStars');

const imdbScore = document.getElementById('imdbScore');
const imdbVotes = document.getElementById('imdbVotes');
const imdbStars = document.getElementById('imdbStars');

const rtCriticScore = document.getElementById('rtCriticScore');
const rtAudienceScore = document.getElementById('rtAudienceScore');
const rtCriticIcon = document.getElementById('rtCriticIcon');
const rtAudienceIcon = document.getElementById('rtAudienceIcon');

// 事件监听
searchBtn.addEventListener('click', handleSearch);
movieInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSearch();
    }
});

// 搜索处理函数
async function handleSearch() {
    let movieName = movieInput.value.trim();
    
    if (!movieName) {
        showError('请输入电影名称');
        return;
    }
    
    // 验证输入 - 移除或转义特殊字符
    // 允许中文、英文、数字、空格和一些基本符号
    const validPattern = /^[\u4e00-\u9fa5a-zA-Z0-9\s\-\':,.!?&]+$/;
    if (!validPattern.test(movieName)) {
        showError('电影名称包含不支持的字符，请使用中文、英文、数字或常见符号');
        return;
    }
    
    // 限制输入长度
    if (movieName.length > 100) {
        showError('电影名称过长，请输入100个字符以内');
        return;
    }
    
    // 重置状态
    hideError();
    hideResults();
    showLoader();
    
    try {
        // 调用后端API
        console.log('正在搜索电影:', movieName);
        
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ movie_name: movieName })
        });
        
        console.log('响应状态:', response.status, response.statusText);
        
        const data = await response.json();
        console.log('响应数据:', data);
        
        if (!response.ok) {
            throw new Error(data.error || `搜索失败 (${response.status})`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // 显示结果
        displayResults(data);
        
    } catch (err) {
        showError(err.message || '搜索出错，请稍后重试');
    } finally {
        hideLoader();
    }
}

// 显示搜索结果
function displayResults(data) {
    // 基本信息
    moviePoster.src = data.poster || 'static/images/no-poster.jpg';
    moviePoster.alt = data.title || '';
    movieTitle.textContent = data.title || '未知电影';
    movieYear.textContent = data.year ? `(${data.year})` : '';
    movieGenre.textContent = data.genre || '未知类型';
    movieDirector.innerHTML = data.director ? `<strong>导演：</strong>${data.director}` : '';
    movieActors.innerHTML = data.actors ? `<strong>主演：</strong>${data.actors}` : '';
    moviePlot.textContent = data.plot || '暂无剧情简介';
    
    // 豆瓣评分
    if (data.douban) {
        doubanScore.textContent = data.douban.score || '-';
        doubanVotes.textContent = formatNumber(data.douban.votes) || '-';
        doubanStars.innerHTML = createStars(data.douban.score);
    } else {
        doubanScore.textContent = '-';
        doubanVotes.textContent = '-';
        doubanStars.innerHTML = '';
    }
    
    // IMDb评分
    if (data.imdb) {
        imdbScore.textContent = data.imdb.score || '-';
        imdbVotes.textContent = formatNumber(data.imdb.votes) || '-';
        imdbStars.innerHTML = createStars(data.imdb.score);
    } else {
        imdbScore.textContent = '-';
        imdbVotes.textContent = '-';
        imdbStars.innerHTML = '';
    }
    
    // 烂番茄评分
    if (data.rottenTomatoes) {
        rtCriticScore.textContent = data.rottenTomatoes.critic ? `${data.rottenTomatoes.critic}%` : '-%';
        rtAudienceScore.textContent = data.rottenTomatoes.audience ? `${data.rottenTomatoes.audience}%` : '-%';
        
        // 更新图标颜色
        updateRTIcon(rtCriticIcon, data.rottenTomatoes.critic);
        updateRTIcon(rtAudienceIcon, data.rottenTomatoes.audience);
    } else {
        rtCriticScore.textContent = '-%';
        rtAudienceScore.textContent = '-%';
    }
    
    showResults();
}

// 创建星级评分
function createStars(score) {
    if (!score || score === '-') return '';
    
    const rating = parseFloat(score);
    const fullStars = Math.floor(rating / 2);
    const hasHalf = (rating / 2) % 1 >= 0.5;
    const emptyStars = 5 - fullStars - (hasHalf ? 1 : 0);
    
    let stars = '';
    
    // 填充满星
    for (let i = 0; i < fullStars; i++) {
        stars += '<span class="star filled">★</span>';
    }
    
    // 半星
    if (hasHalf) {
        stars += '<span class="star half">★</span>';
    }
    
    // 空星
    for (let i = 0; i < emptyStars; i++) {
        stars += '<span class="star">★</span>';
    }
    
    return stars;
}

// 更新烂番茄图标
function updateRTIcon(icon, score) {
    if (!score || score === '-') {
        icon.style.color = '#ccc';
        return;
    }
    
    const percentage = parseInt(score);
    if (percentage >= 60) {
        icon.style.color = '#FA320A'; // 新鲜
    } else {
        icon.style.color = '#0AC855'; // 腐烂
    }
}

// 格式化数字
function formatNumber(num) {
    if (!num) return null;
    
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// UI控制函数
function showLoader() {
    loader.classList.remove('hidden');
}

function hideLoader() {
    loader.classList.add('hidden');
}

function showError(message) {
    errorText.textContent = message;
    error.classList.remove('hidden');
}

function hideError() {
    error.classList.add('hidden');
}

function showResults() {
    results.classList.remove('hidden');
}

function hideResults() {
    results.classList.add('hidden');
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    movieInput.focus();
});