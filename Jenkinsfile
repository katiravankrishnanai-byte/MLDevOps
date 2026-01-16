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
      docker build -t katiravan/mldevops:%TAG% .
    '''
  }
}
    stage('Push Image') {
  steps {
    withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'U', passwordVariable: 'P')]) {
      bat '''
        @echo on
        set TAG=%GIT_COMMIT:~0,7%
        echo Logging in...
        echo %P% | docker login -u %U% --password-stdin
        echo Pushing...
        docker push katiravan/mldevops:%TAG%
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
         kubectl apply -f k8s/namespace.yaml
      kubectl apply -f k8s/deployment.yaml
      kubectl apply -f k8s/service.yaml
      kubectl rollout status deploy/mldevops -n mldevops
      kubectl get pods -n mldevops
      '''
    }
  }
}

  }
}
