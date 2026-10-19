pipeline {
    agent {
        node {
            label 'ai-agent-node'
        }
    }

    environment {
        IMAGE_NAME = "34.21.186.237:5050/root/ai-agent:${BUILD_NUMBER}"
        GEMINI_API_KEY = credentials('GEMINI_API_KEY')
        GITLAB_TOKEN = credentials('gitlab-token')
    }

    stages {
        // =========================================================================
        // QUALITY GATES: CHẠY TEST SONG SONG
        // =========================================================================
        stage('Quality Gates: Parallel Testing') {
            failFast true
            parallel {
                stage('Test Backend') {
                    steps {
                        echo '🧪 Đang chạy kiểm thử Backend...'
                        sh 'bash scripts/test-backend.sh'
                    }
                }
                stage('Test Frontend') {
                    steps {
                        echo '📦 Đang kiểm tra biên dịch Frontend...'
                        sh 'bash scripts/test-frontend.sh'
                    }
                }
            }
        }

        // =========================================================================
        // PHÁT HÀNH: CHỈ CHẠY KHI TẤT CẢ TEST ĐỀU THÀNH CÔNG
        // =========================================================================
        stage('Build & Push Image') {
            steps {
                sh 'bash scripts/build.sh'
            }
        }

        stage('Deploy') {
            steps {
                sh 'bash scripts/deploy.sh'
            }
        }
    }
}