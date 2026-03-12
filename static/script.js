document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('video-file');
    const fileLabel = document.getElementById('file-label');
    const submitBtn = document.getElementById('submit-btn');
    const uploadForm = document.getElementById('upload-form');
    
    const uploadSection = document.getElementById('upload-section');
    const loadingSection = document.getElementById('loading-section');
    const resultSection = document.getElementById('result-section');
    
    const resultVideo = document.getElementById('result-video');
    const resultText = document.getElementById('result-text');
    const resetBtn = document.getElementById('reset-btn');

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            fileLabel.textContent = e.target.files[0].name;
            submitBtn.disabled = false;
        } else {
            fileLabel.textContent = 'Chọn Video (Click hoặc Kéo Thả)';
            submitBtn.disabled = true;
        }
    });

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (fileInput.files.length === 0) return;
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('video', file);

        uploadSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');

        try {
            const response = await fetch('/api/summarize', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Lỗi kết nối server');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let partialData = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = (partialData + chunk).split('\n');
                partialData = lines.pop();

                for (const rawLine of lines) {
                    const line = rawLine.trim();
                    if (line === '') continue;

                    if (line.startsWith('__RESULT__:')) {
                        const jsonStr = line.substring(11);
                        try {
                            const data = JSON.parse(jsonStr);
                            // Success
                            resultVideo.src = data.video_url;
                            resultText.textContent = data.text;
                            
                            loadingSection.classList.add('hidden');
                            resultSection.classList.remove('hidden');
                            return;
                        } catch (parseError) {
                            console.error('JSON Parse Error. Data:', jsonStr);
                            throw new Error('Lỗi dữ liệu từ server: ' + parseError.message);
                        }
                    } else if (line.startsWith('__ERROR__:')) {
                        throw new Error(line.substring(10));
                    }
                    // Logs are ignored as per user request
                }
            }
        } catch (error) {
            alert('Lỗi: ' + error.message);
            loadingSection.classList.add('hidden');
            uploadSection.classList.remove('hidden');
            fileInput.value = '';
            fileLabel.textContent = 'Chọn Video (Click hoặc Kéo Thả)';
            submitBtn.disabled = true;
        }
    });

    resetBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        fileInput.value = '';
        fileLabel.textContent = 'Chọn Video (Click hoặc Kéo Thả)';
        submitBtn.disabled = true;
        resultVideo.src = '';
        resultText.textContent = '';
    });
});
