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
    
    stage('Build Image') {
  steps {
    bat '''
      @echo on
      set TAG=%GIT_COMMIT:~0,7%
      docker build -t YOUR_REGISTRY/your-app:%TAG% .
    '''
  }
}
    stage('Push Image') {
  steps {
    withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'U', passwordVariable: 'P')]) {
      bat '''
        @echo on
        set TAG=%GIT_COMMIT:~0,7%
        echo %P% | docker login -u %U% --password-stdin
        docker push YOUR_REGISTRY/your-app:%TAG%
      '''
    }
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
    stage('Deploy (Smoke)') {
  steps {
    withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
      bat '''
        @echo on
        set KUBECONFIG=%KUBECONFIG_FILE%
        kubectl apply -f k8s/
        kubectl rollout status deploy/your-deploy -n your-ns
      '''
    }
  }
}
  }
}
