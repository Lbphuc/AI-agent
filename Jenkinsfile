pipeline {
    agent {
        node {
            label 'ai-agent-node'
        }
    }

    environment {
        // Gắn BUILD_NUMBER vào tag image thay vì dùng cố định latest
        IMAGE_NAME = "34.21.186.237:5050/root/ai-agent:${BUILD_NUMBER}"
        GEMINI_API_KEY = credentials('GEMINI_API_KEY')
        GITLAB_TOKEN = credentials('gitlab-token')
    }

    stages {
        stage('Build & Push Image') {
            steps {
                // scripts/build.sh sẽ dùng biến IMAGE_NAME và GITLAB_TOKEN
                sh 'bash scripts/build.sh'
            }
        }

        stage('Deploy') {
            steps {
                // Nếu ai-agent-node CHÍNH LÀ máy 136.85.54.207 (chạy deploy tại chỗ):
                sh 'bash scripts/deploy.sh'
                
                // HOẶC nếu Jenkins agent nằm ở máy khác và cần SSH sang 136.85.54.207:
                // sh '''
                //     ssh -o StrictHostKeyChecking=no phuc@136.85.54.207 \
                //       "BUILD_NUMBER=${BUILD_NUMBER} GEMINI_API_KEY='${GEMINI_API_KEY}' bash -s" < scripts/deploy.sh
                // '''
            }
        }
    }
}