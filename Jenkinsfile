pipeline {
  agent any

  stages {
    stage('Environment Verification') {
      steps {
        bat '''
          @echo on
          whoami
          git --version
          docker --version
          kubectl version --client
        '''
      }
    }

    stage('Docker Daemon Check') {
      steps {
        bat '''
          @echo on
          docker ps
        '''
      }
    }

    stage('Kubernetes Access Check') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%
            kubectl config current-context
            kubectl get nodes
          '''
        }
      }
    }
  }
}
