pipeline {
  agent any

  environment {
    IMAGE_REPO = "katiravan/mldevops"   		// match with image
    NAMESPACE  = "mldevopskatir"     // match your namespace.yml
    APP_NAME   = "mldevops"        // must match Deployment name + container name
    SERVICE    = "mldevops"    	// must match Service name
  }

  options { 
    timestamps()
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        bat 'git --version'
        bat 'docker --version'
        bat 'kubectl version --client=true'
      }
    }

    stage('Compute Tags') {
      steps {
        bat '''
          @echo on
          for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i
          echo SHORTSHA=%SHORTSHA%

          rem If build is running on a git tag (e.g. v1.0.0), capture it
          for /f %%t in ('git describe --tags --exact-match 2^>nul') do set RELTAG=%%t
          echo RELTAG=%RELTAG%
        '''
      }
    }

    stage('QA (Lint + Unit Tests)') {
      steps {
        bat '''
          @echo on
          python --version
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest 

          if not exist reports mkdir reports
          python -m pytest -q --junitxml=reports\\test-results.xml
          dir reports
        '''
      }
      post {
        always {
          junit 'reports/test-results.xml'
          archiveArtifacts artifacts: 'reports/test-results.xml', fingerprint: true
        }
      }
    }

    stage('Build Image') {
      steps {
        bat '''
          @echo on
          for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i

          docker build -t %IMAGE_REPO%:git-%SHORTSHA% .

          rem If this is a release tag build, also tag image with vX.Y.Z
          for /f %%t in ('git describe --tags --exact-match 2^>nul') do (
            docker tag %IMAGE_REPO%:git-%SHORTSHA% %IMAGE_REPO%:%%t
          )
        '''
      }
    }

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'registry-creds', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          bat '''
            @echo on
            for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i

            echo %DOCKER_PASS% | docker login -u %DOCKER_USER% --password-stdin

            docker push %IMAGE_REPO%:git-%SHORTSHA%

            for /f %%t in ('git describe --tags --exact-match 2^>nul') do (
              docker push %IMAGE_REPO%:%%t
            )
          '''
        }
      }
    }

    stage('Deploy to Kubernetes (Apply + Set Image)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            rem Apply base manifests
            kubectl apply -f k8s\\namespace.yml
            kubectl apply -f k8s\\deployment.yml
            kubectl apply -f k8s\\service.yml

            rem Update image to immutable commit tag
            for /f %%i in ('git rev-parse --short=7 HEAD') do set SHORTSHA=%%i
            kubectl -n %NAMESPACE% set image deploy/%APP_NAME% %APP_NAME%=%IMAGE_REPO%:git-%SHORTSHA%
          '''
        }
      }
    }

    stage('Rollout Gate (Must Succeed)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            kubectl -n %NAMESPACE% rollout status deploy/%APP_NAME% --timeout=180s
            kubectl -n %NAMESPACE% get pods -o wide
            kubectl -n %NAMESPACE% get svc
          '''
        }
      }
    }

    stage('Smoke Test (/health)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            rem Call service inside cluster
            kubectl -n %NAMESPACE% run curl --rm -i --restart=Never --image=curlimages/curl -- ^
              curl -sS http://%SERVICE%:8000/health
          '''
        }
      }
    }

    stage('Load Test (k6)') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          bat '''
            @echo on
            set KUBECONFIG=%KUBECONFIG_FILE%

            rem Create/Update configmap with k6 script
            kubectl -n %NAMESPACE% create configmap k6-script --from-file=loadtest\\k6.js --dry-run=client -o yaml | kubectl apply -f -

            rem Run k6 inside cluster against ClusterIP service
            kubectl -n %NAMESPACE% run k6 --rm -i --restart=Never --image=grafana/k6:latest -- ^
              run -e BASE_URL=http://%SERVICE%:8000 k6.js
          '''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'k8s/**/*,loadtest/**/*,Dockerfile,Jenkinsfile,requirements.txt,README.md', fingerprint: true
    }
  }
}
