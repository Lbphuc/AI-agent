pipeline {
    agent {
        node {
            label 'ai-agent-node'
        }
    }

    environment {
        IMAGE_NAME = '34.21.186.237:5050/root/ai-agent:latest'
        OPENAI_API_KEY = credentials('my-openai-key-id')
        GITLAB_TOKEN = credentials('gitlab-token')
    }

    stages {
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